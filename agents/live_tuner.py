"""agents/live_tuner.py — Autonomous live tuning agent daemon.

The LiveTunerAgent runs continuously, polls the system every N seconds,
detects which workload category is dominant (game, browser, compiler, etc.),
looks up the best scheduler parameters for that category from the sweep
database, and applies them through the SchedulerController safety pipeline.
"""
from __future__ import annotations

import logging
import signal
import time
from typing import Any, Dict, Optional, Tuple

from monitor.collector import Monitor
from scheduler.controller import SchedulerController
from scheduler.exceptions import RecoveryError
from scheduler.registry import ParameterRegistry
from storage.db import StorageBackend
from workload.classifier import ProcessClassifier
from workload.categories import CATEGORY_TO_BENCHMARK_TYPE

logger = logging.getLogger(__name__)


class LiveTunerAgent:
    """Autonomous agent that watches running apps and applies tuned scheduler params.

    Args:
        monitor:         Monitor instance (reads /proc snapshots).
        controller:      SchedulerController for safe sysctl writes.
        storage:         StorageBackend pointing at the sweep database.
        registry:        ParameterRegistry (for sysctl-path -> name mapping).
        poll_interval:   Seconds between observe-apply cycles (default 10).
        dry_run:         If True, skips the actual controller.apply_parameters() call.
        cache_ttl:       Seconds to cache best_params lookups (default 300).
    """

    def __init__(
        self,
        monitor: Monitor,
        controller: SchedulerController,
        storage: StorageBackend,
        registry: ParameterRegistry,
        poll_interval: float = 10.0,
        dry_run: bool = False,
        cache_ttl: float = 300.0,
        watchdog=None,
    ) -> None:
        self.monitor = monitor
        self.controller = controller
        self.storage = storage
        self.registry = registry
        self.poll_interval = poll_interval
        self.dry_run = dry_run
        self.cache_ttl = cache_ttl
        self.watchdog = watchdog
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")

        self._classifier = ProcessClassifier()
        self._running = False

        # Hysteresis state
        self._last_category: Optional[str] = None
        self._last_params: Optional[Dict[str, Any]] = None

        # Best-params cache:  workload_type -> (params_dict, fetched_at)
        self._cache: Dict[str, Tuple[Optional[Dict[str, Any]], float]] = {}

    def run_forever(self) -> None:
        """Start the main polling loop. Exits cleanly on SIGINT / SIGTERM."""
        self._running = True
        previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            for sig in previous:
                signal.signal(sig, self._handle_stop)
            logger.info("LiveTunerAgent started interval=%.1fs dry_run=%s",
                        self.poll_interval, self.dry_run)
            while self._running:
                try:
                    self._tick()
                except RecoveryError:
                    raise
                except Exception:
                    logger.exception("Unexpected error in tuning tick — continuing")
                if self._running:
                    time.sleep(self.poll_interval)
        finally:
            self._running = False
            for sig, handler in previous.items():
                signal.signal(sig, handler)
            logger.info("LiveTunerAgent stopped.")

    def run_once(self) -> Dict[str, Any]:
        """Run exactly one observe-classify-apply cycle. Returns a status dict."""
        return self._tick()

    def _tick(self) -> Dict[str, Any]:
        """One observe -> classify -> lookup -> (apply) cycle."""
        if self.watchdog is not None:
            if self.watchdog.timed_out:
                raise RecoveryError("Live tuner watchdog expired")
            self.watchdog.ping()
        # 1. Observe
        snapshot = self.monitor.read_snapshot()

        # 2. Classify workload
        fingerprint = self._classifier.fingerprint(snapshot)
        category = fingerprint.primary_category
        workload_type = CATEGORY_TO_BENCHMARK_TYPE.get(category, "mixed")

        top_proc = fingerprint.top_processes[0][0] if fingerprint.top_processes else "(none)"
        logger.info(
            "[tick] category=%r  workload=%r  top_proc=%r",
            category, workload_type, top_proc,
        )

        # 3. Look up best params for this workload type
        best = self._get_best_params(workload_type)

        status = {
            "category": category,
            "workload_type": workload_type,
            "top_proc": top_proc,
            "best_found": best is not None,
            "applied": False,
            "skipped_reason": None,
            "classification_basis": fingerprint.measurement_basis,
            "classified_cpu_fraction": fingerprint.classified_cpu_fraction,
        }

        if fingerprint.observed_cpu_ticks == 0 or fingerprint.classified_cpu_fraction < 0.5:
            status["skipped_reason"] = "insufficient_workload_evidence"
            return status

        if best is None:
            msg = f"No sweep data for workload_type={workload_type!r} — run run_sweep.py first"
            logger.warning(msg)
            status["skipped_reason"] = "no_sweep_data"
            return status

        # 4. Hysteresis check
        params_to_apply = self._sysctl_to_registry(best["sched_params"])
        if not params_to_apply:
            logger.warning("best_params has no registry-mapped params — skipping")
            status["skipped_reason"] = "no_registry_params"
            return status

        if self._last_category == category and self._params_equal(params_to_apply, self._last_params):
            logger.info("  Same category & params as last tick — skipping apply (hysteresis)")
            status["skipped_reason"] = "hysteresis"
            return status

        # 5. Apply
        score = best.get("score", 0.0)
        logger.info(
            "  Applying %d params for category=%r (sweep score=%.4f%s)",
            len(params_to_apply), category, score,
            " dry-run" if self.dry_run else "",
        )
        for name, val in params_to_apply.items():
            logger.debug("    %s = %s", name, val)

        if not self.dry_run:
            try:
                self.controller.apply_parameters(params_to_apply)
                self._last_category = category
                self._last_params = params_to_apply
                status["applied"] = True
                logger.info("  Applied successfully.")
            except RecoveryError:
                raise
            except Exception as exc:
                logger.error("  apply_parameters failed: %s", exc)
                status["skipped_reason"] = f"apply_error: {exc}"
                # The controller restores failed transactions itself. A second
                # rollback would undo an earlier successful configuration.
        else:
            self._last_category = category
            self._last_params = params_to_apply
            status["applied"] = True  # logically applied in dry-run

        return status

    def _get_best_params(self, workload_type: str) -> Optional[Dict[str, Any]]:
        """Return cached or freshly fetched best params for *workload_type*."""
        now = time.monotonic()
        cached = self._cache.get(workload_type)
        if cached is not None:
            params, fetched_at = cached
            if (now - fetched_at) < self.cache_ttl:
                return params

        params = self.storage.best_params_for_workload(workload_type)
        self._cache[workload_type] = (params, now)
        return params

    def _sysctl_to_registry(self, sched_params: Dict[str, Any]) -> Dict[str, Any]:
        """Convert sysctl-path keyed map to registry logical name keyed map."""
        out: Dict[str, Any] = {}
        for meta in self.registry.get_all():
            if meta.path in sched_params:
                try:
                    out[meta.name] = meta.type(sched_params[meta.path])
                except Exception:
                    continue
        return out

    @staticmethod
    def _params_equal(a: Optional[Dict[str, Any]], b: Optional[Dict[str, Any]]) -> bool:
        if a is None or b is None:
            return False
        return a == b

    def _handle_stop(self, signum, frame) -> None:
        logger.info("Signal %d received — stopping after current tick", signum)
        self._running = False

    def invalidate_cache(self) -> None:
        """Force re-fetch of all best-params on the next tick."""
        self._cache.clear()
