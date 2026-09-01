from typing import Dict, Any, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class SecondaryValidator:
    """Independent second-check validator to ensure safe parameter ranges.

    This validator is completely independent of the ParameterRegistry and
    Validator — it defines its own hard limits as a last line of defence
    before values reach the kernel.  All 8 known tunable parameters are
    covered (§1.4).
    """

    def __init__(self, extra_limits: Optional[Dict[str, Tuple[float, float]]] = None):
        # Hardcoded ultimate safety limits independent of the registry.
        # Covers every parameter from the scheduler.yaml, dashboard, and
        # training script registries (§1.4, §5.1).
        self.hard_limits: Dict[str, Tuple[float, float]] = {
            # CFS granularity params (used by training)
            "kernel.sched_min_granularity_ns":       (10_000, 1_000_000_000),
            "kernel.sched_wakeup_granularity_ns":     (10_000, 1_000_000_000),
            # RT scheduling params
            "kernel.sched_rr_timeslice_ms":           (1, 2_000),
            "kernel.sched_rt_period_us":              (1, 1_000_000),
            "kernel.sched_rt_runtime_us":             (-1, 1_000_000),
            # CFS bandwidth
            "kernel.sched_cfs_bandwidth_slice_us":    (1, 100_000),
            # Autogroup (boolean-like)
            "kernel.sched_autogroup_enabled":          (0, 1),
            # UCLAMP
            "kernel.sched_util_clamp_max":             (0, 1024),
            "kernel.sched_util_clamp_min":             (0, 1024),
            # Schedstats (boolean-like)
            "kernel.sched_schedstats":                 (0, 1),
        }
        if extra_limits:
            self.hard_limits.update(extra_limits)

    def validate(self, path: str, value: Any) -> bool:
        """Return True if value is within hard limits, False otherwise.

        Parameters not present in hard_limits are allowed through — the
        validator is a safety net, not a gatekeeper for unknown paths.
        """
        if path not in self.hard_limits:
            return True
        min_val, max_val = self.hard_limits[path]
        try:
            val = float(value)
            if val < min_val or val > max_val:
                logger.error(
                    "Safety violation: %s=%s outside limits %s-%s",
                    path, value, min_val, max_val,
                )
                return False
        except (ValueError, TypeError):
            logger.error(
                "Safety violation: %s=%s is not a valid number", path, value,
            )
            return False
        return True

    def validate_batch(self, params: Dict[str, Any]) -> bool:
        """Validate a dict of {sysctl_path: value} pairs. Returns False on first failure."""
        for path, value in params.items():
            if not self.validate(path, value):
                return False
        return True
