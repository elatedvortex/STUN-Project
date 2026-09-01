"""
ActionMapper — translates a raw RL agent action into a parameter dict
ready for SchedulerController.apply_parameters().

Two modes (set at env construction time):

  "discrete"   — Discrete(n_params * 2 + 1)
                 0             = no-op (do nothing)
                 1 .. n_params = increment param[i] by one step
                 n_params+1 .. 2*n_params = decrement param[i] by one step
                 Step size = (max - min) / n_steps, clipped to [min, max].

  "continuous" — Box(low=-1, high=1, shape=(n_params,))
                 -1 → min_value, +1 → max_value (linear map, clipped).

The mapper tracks the current value of each parameter internally in
discrete mode (since discrete actions are relative). Call reset_state()
at each episode start (the env does this automatically in reset()).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import gymnasium
from gymnasium import spaces

from scheduler.registry import ParameterRegistry
from scheduler.types import ParameterMeta


class ActionMapper:
    def __init__(
        self,
        registry: ParameterRegistry,
        mode: str = "discrete",
        n_steps: int = 20,
    ) -> None:
        if mode not in ("discrete", "continuous"):
            raise ValueError(f"Unknown action mode {mode!r}; expected 'discrete' or 'continuous'")
        self._mode = mode
        self._n_steps = n_steps
        self._params: List[ParameterMeta] = registry.get_all()
        self._n_params = len(self._params)
        # Internal current-value state for discrete mode
        self._current_values: List[float] = []
        self.reset_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def action_space(self) -> gymnasium.Space:
        if self._mode == "discrete":
            # 0 = noop, 1..n = increment, n+1..2n = decrement
            return spaces.Discrete(self._n_params * 2 + 1)
        else:
            return spaces.Box(
                low=-1.0,
                high=1.0,
                shape=(self._n_params,),
                dtype=np.float32,
            )

    def decode(self, action: int | np.ndarray) -> Dict[str, Any]:
        """Return a dict suitable for SchedulerController.apply_parameters().

        Returns {} for a no-op action.
        """
        if self._mode == "discrete":
            return self._decode_discrete(int(action))
        else:
            return self._decode_continuous(np.asarray(action, dtype=np.float32))

    def reset_state(self, current_values: Optional[Dict[str, Any]] = None) -> None:
        """Reset internal tracking of current parameter values.

        Called by the env in reset(). current_values can be used to seed
        the tracker from actual live kernel values; if None, each parameter
        starts at the midpoint of its range.
        """
        self._current_values = []
        for meta in self._params:
            if current_values and meta.name in current_values:
                self._current_values.append(float(current_values[meta.name]))
            else:
                lo = float(meta.min_value) if meta.min_value is not None else 0.0
                hi = float(meta.max_value) if meta.max_value is not None else 1.0
                self._current_values.append((lo + hi) / 2.0)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _decode_discrete(self, action: int) -> Dict[str, Any]:
        if action == 0 or self._n_params == 0:
            return {}

        # actions 1..n_params → increment; n_params+1..2*n_params → decrement
        if 1 <= action <= self._n_params:
            idx = action - 1
            direction = +1
        else:
            idx = action - self._n_params - 1
            direction = -1

        meta = self._params[idx]
        lo = float(meta.min_value) if meta.min_value is not None else 0.0
        hi = float(meta.max_value) if meta.max_value is not None else 1.0
        step = (hi - lo) / self._n_steps

        new_value = self._current_values[idx] + direction * step
        new_value = max(lo, min(hi, new_value))
        self._current_values[idx] = new_value

        return {meta.name: meta.type(new_value)}

    def _decode_continuous(self, action: np.ndarray) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for i, meta in enumerate(self._params):
            lo = float(meta.min_value) if meta.min_value is not None else 0.0
            hi = float(meta.max_value) if meta.max_value is not None else 1.0
            a = float(np.clip(action[i], -1.0, 1.0))
            # map [-1, 1] → [lo, hi]
            value = lo + (a + 1.0) / 2.0 * (hi - lo)
            value = max(lo, min(hi, value))
            result[meta.name] = meta.type(value)
        return result
