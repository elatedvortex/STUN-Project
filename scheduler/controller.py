import logging
from typing import Any, Dict, Optional
from scheduler.registry import ParameterRegistry
from scheduler.validator import Validator
from scheduler.writer import Writer
from scheduler.rollback import RollbackStack
from scheduler.profile import ProfileStore
from scheduler.exceptions import ValidationError

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

    def apply_parameters(self, params: Dict[str, Any]) -> None:
        """Validate and write parameters through the full safety pipeline.

        Validation order:
          1. Primary Validator  — registry bounds check
          2. SecondaryValidator — independent hard-limit safety check
          3. Writer             — sysctl write + readback verify
          4. Audit trail        — persist to SQLite (if storage is wired)
        """
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

        # Snapshot current state for rollback
        current_state = {}
        for name in params.keys():
            meta = self.registry.get(name)
            backend = self.writer.backends[meta.backend]
            current_state[name] = meta.type(backend.read(meta.path))

        self.rollback_stack.push(current_state)

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

        logger.info("Successfully applied %d parameters.", len(params))

    def rollback(self) -> None:
        state = self.rollback_stack.pop()
        if not state:
            logger.warning("Rollback stack is empty, nothing to rollback.")
            return

        for name, value in state.items():
            self.writer.write_and_verify(name, value)
        logger.info("Successfully rolled back to previous state.")

    def apply_profile(self, profile_name: str) -> None:
        profile = self.profile_store.get_profile(profile_name)
        if profile is None:
            raise ValueError("Profile %s not found" % profile_name)
        self.apply_parameters(profile)
