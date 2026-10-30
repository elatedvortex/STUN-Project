"""
StateBuilder — converts a SystemSnapshot into a fixed-length float32
numpy array suitable for use as a Gymnasium Box observation.

The dimension is determined at construction time from the ParameterRegistry,
so adding new tunables automatically extends the obs space without touching
any other module.

All values are normalised to [0, 1]. None fields (unavailable on this
kernel/container) become 0.0, matching the monitor's "None means unavailable,
not zero" convention while keeping the obs space simple.
"""

from __future__ import annotations

import os
import numpy as np

from typing import TYPE_CHECKING, Optional

from monitor.types import SystemSnapshot
from scheduler.registry import ParameterRegistry

if TYPE_CHECKING:
    from workload.context import WorkloadContextBuilder


# Upper bounds used for normalisation
_MAX_CTXT_DELTA = 1_000_000.0
_MAX_PROCS = 1_000.0


class StateBuilder:
    """Converts a SystemSnapshot to a normalised float32 np.ndarray.

    Layout
    ------
    Index  Field                     Normaliser
    0      cpu_util_pct              ÷ 100
    1      load_avg_1                ÷ num_cpus
    2      load_avg_5                ÷ num_cpus
    3      mem_util_pct              ÷ 100
    4      ctxt_switches_delta       ÷ 1_000_000
    5      runnable_procs            ÷ 1_000
    6..N   sched_params (per param)  ÷ param.max_value
    """

    _FIXED_FIELDS = 6

    def __init__(
        self,
        registry: ParameterRegistry,
        num_cpus: Optional[int] = None,
    ) -> None:
        self._registry = registry
        self._num_cpus = float(num_cpus or os.cpu_count() or 1)
        # Ordered list — order matches insertion order of registry, which is
        # stable across a run (ParameterRegistry uses a plain dict internally).
        self._param_names = [p.name for p in registry.get_all()]

    @property
    def obs_dim(self) -> int:
        """Length of the observation vector this builder produces."""
        return self._FIXED_FIELDS + len(self._param_names)

    def build(self, snapshot: SystemSnapshot) -> np.ndarray:
        """Return a normalised float32 array of shape (obs_dim,)."""
        obs = np.zeros(self.obs_dim, dtype=np.float32)

        # --- fixed slots ---
        obs[0] = _clip((snapshot.cpu_util_pct or 0.0) / 100.0)
        obs[1] = _clip((snapshot.load_avg_1 or 0.0) / self._num_cpus)
        obs[2] = _clip((snapshot.load_avg_5 or 0.0) / self._num_cpus)
        obs[3] = _clip((snapshot.mem_util_pct or 0.0) / 100.0)
        obs[4] = _clip((snapshot.ctxt_switches_delta or 0.0) / _MAX_CTXT_DELTA)
        obs[5] = _clip((snapshot.runnable_procs or 0.0) / _MAX_PROCS)

        # --- per-parameter slots ---
        sched_params = snapshot.sched_params or {}
        for i, name in enumerate(self._param_names):
            meta = self._registry.get(name)
            # Monitor sources use sysctl paths; accept logical names for legacy
            # snapshots too. Looking up only names silently zeroed real inputs.
            raw = float(sched_params.get(meta.path, sched_params.get(name, 0.0)))
            max_val = float(meta.max_value) if meta.max_value else 1.0
            obs[self._FIXED_FIELDS + i] = _clip(raw / max_val if max_val != 0 else 0.0)

        return obs


def _clip(v: float) -> float:
    return max(0.0, min(1.0, v))
