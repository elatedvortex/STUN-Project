import logging
import threading
from contextlib import nullcontext
from typing import Any, Dict, Optional
from scheduler.registry import ParameterRegistry
from scheduler.validator import Validator
from scheduler.writer import Writer
from scheduler.rollback import RollbackStack
from scheduler.profile import ProfileStore
from scheduler.exceptions import ValidationError, RecoveryError
from scheduler.backend import SysctlBackend
from scheduler.constraints import ordered_update
from safety.lease import HostLease

logger = logging.getLogger(__name__)


class SchedulerController:
    """Validates, writes, and maintains rollback stack for scheduler parameters.

    Supports optional SecondaryValidator (safety module) and StorageBackend
    (audit trail) injection for defence-in-depth and persistence.
    """

    def __init__(
        self,
        registry: ParameterRegistry,
        validator: Validator,
        writer: Writer,
        rollback_stack: RollbackStack,
        profile_store: ProfileStore,
        secondary_validator=None,
        storage_backend=None,
    ):
        self.registry = registry
        self.validator = validator
        self.writer = writer
        self.rollback_stack = rollback_stack
        self.profile_store = profile_store
        self._secondary_validator = secondary_validator
        self._storage = storage_backend
        self._lock = threading.RLock()
        self._recovery_required = False
        self._halted = False
        self._host_lease = HostLease() if any(
            isinstance(backend, SysctlBackend) for backend in self.writer.backends.values()
        ) else None

    def exclusive(self):
        """Hold the host lease across a live session; fakes need no host lease."""
        return self._host_lease.hold() if self._host_lease else nullcontext()

    def read_state(self) -> Dict[str, Any]:
        """Read every registered value, failing if any cannot be captured."""
        with self._lock, self.exclusive():
            return {
                meta.name: meta.type(self.writer.backends[meta.backend].read(meta.path))
                for meta in self.registry.get_all()
            }

    def _restore(self, state: Dict[str, Any]) -> None:
        try:
            state = ordered_update(self.registry, self.writer.backends, state)
        except Exception as exc:
            self._recovery_required = True
            raise RecoveryError("Could not plan baseline restoration") from exc
        errors = []
        for name, value in state.items():
            try:
                self.writer.write_and_verify(name, value)
            except Exception as exc:
                errors.append(f"{name}: {exc}")
        self._recovery_required = bool(errors)
        if errors:
            raise RecoveryError("Restoration failed: " + "; ".join(errors))

    def restore_state(self, state: Dict[str, Any]) -> None:
        """Restore a captured baseline, retaining history if restoration fails."""
        with self._lock, self.exclusive():
            if set(state) != {meta.name for meta in self.registry.get_all()}:
                raise ValueError("Baseline must contain every registered parameter")
            self._restore(state)
            self.rollback_stack.clear()

    def halt_and_restore(self, state: Dict[str, Any]) -> None:
        """Stop future writes before watchdog restoration, under the same lock."""
        with self._lock, self.exclusive():
            self._halted = True
            self.restore_state(state)

    def apply_parameters(self, params: Dict[str, Any]) -> None:
        with self._lock, self.exclusive():
            if self._halted:
                raise RecoveryError("Tuning halted by watchdog; start a new session after recovery")
            if self._recovery_required:
                raise RecoveryError("Restore the saved state before applying more parameters")
            self._apply_parameters(params)

    def _apply_parameters(self, params: Dict[str, Any]) -> None:
        """Validate and write parameters through the full safety pipeline.

        Validation order:
          1. Primary Validator  — registry bounds check
          2. SecondaryValidator — independent hard-limit safety check
          3. Writer             — sysctl write + readback verify
          4. Audit trail        — persist to SQLite (if storage is wired)
        """
        if not params:
            return
        # Layer 1: Primary validation (registry bounds)
        self.validator.validate(params)

        # Layer 2: Secondary safety validation (independent hard limits)
        if self._secondary_validator is not None:
            for name, value in params.items():
                meta = self.registry.get(name)
                if not self._secondary_validator.validate(meta.path, value):
                    raise ValidationError(
                        "SecondaryValidator rejected %s=%s (path=%s)"
                        % (name, value, meta.path)
                    )

        params = ordered_update(self.registry, self.writer.backends, params)

        # Snapshot current state for rollback
        current_state = {}
        for name in params.keys():
            meta = self.registry.get(name)
            backend = self.writer.backends[meta.backend]
            current_state[name] = meta.type(backend.read(meta.path))

        self.rollback_stack.push(current_state)

        # Restore the complete pre-write state if any write/readback fails.
        try:
            self._write_parameters(params, current_state)
        except BaseException:
            self.rollback()
            raise

        logger.info("Successfully applied %d parameters.", len(params))

    def _write_parameters(self, params, current_state):
        # Write and verify each parameter
        for name, value in params.items():
            meta = self.registry.get(name)
            old_value = current_state.get(name)
            success = True
            error_msg = ""

            try:
                self.writer.write_and_verify(name, value)
            except Exception as exc:
                success = False
                error_msg = str(exc)
                raise
            finally:
                # Layer 4: Persist audit trail (if storage is wired)
                if self._storage is not None:
                    try:
                        self._storage.write_applied_config(
                            param_name=name,
                            sysctl_path=meta.path,
                            new_value=str(value),
                            old_value=str(old_value) if old_value is not None else None,
                            source="controller",
                            success=success,
                            error_message=error_msg,
                        )
                    except Exception:
                        logger.warning(
                            "Failed to persist audit trail for %s", name,
                            exc_info=True,
                        )

    def rollback(self) -> None:
        with self._lock, self.exclusive():
            state = self.rollback_stack.peek()
            if not state:
                return
            self._restore(state)
            self.rollback_stack.pop()
            logger.info("Successfully rolled back to previous state.")

    def apply_profile(self, profile_name: str) -> None:
        profile = self.profile_store.get_profile(profile_name)
        if profile is None:
            raise ValueError("Profile %s not found" % profile_name)
        self.apply_parameters(profile)
