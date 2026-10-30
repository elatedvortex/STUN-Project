"""
LinuxSchedulerEnv — Gymnasium Env wrapping M1 monitor + M2 scheduler.

Observation space : Box(low=0, high=1, shape=(obs_dim,), dtype=float32)
                    Normalised system state vector from StateBuilder.

Action space      : Discrete(n_params * 2 + 1)  [default]
                    or Box(-1, 1, (n_params,))   [mode="continuous"]

Reward            : Scalar float from RewardShaper, driven by a
                    BenchmarkRunner result.

Episode lifecycle
-----------------
  reset()  → rolls back to baseline, resets action mapper state, takes
              one snapshot, returns (obs, {}).
  step(a)  → decode action → apply params (catching ValidationError) →
              run benchmark → ping watchdog → take snapshot → return
              (obs, reward, terminated, False, info).

The env does NOT start or stop the Watchdog thread — that's the caller's
responsibility (EpisodeRunner in core/loop.py, or the test itself). This
keeps the env fully unit-testable without threading.

Accepted by gymnasium.utils.env_checker.check_env().
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np
import gymnasium
from gymnasium import spaces

from monitor.collector import Monitor
from monitor.types import SystemSnapshot
from scheduler import SchedulerController, ParameterRegistry
from scheduler.exceptions import ValidationError, RecoveryError
from safety.watchdog import Watchdog
from benchmarks.base import BenchmarkRunner
from rl.state import StateBuilder
from rl.action import ActionMapper
from rl.reward import RewardShaper

logger = logging.getLogger(__name__)


class LinuxSchedulerEnv(gymnasium.Env):
    """Gymnasium environment for Linux scheduler parameter optimisation.

    Parameters
    ----------
    controller : SchedulerController
        M2 controller — validates, writes, maintains rollback stack.
    monitor : Monitor
        M1 monitor — produces SystemSnapshot observations.
    benchmark : BenchmarkRunner
        Reward source — any adapter from benchmarks/.
    registry : ParameterRegistry
        Defines the tunable parameter space (must match controller's registry).
    watchdog : Watchdog | None
        Optional watchdog. Must be started/stopped by the caller.
    action_mode : "discrete" | "continuous"
        Action space type. Default is "discrete" (simpler credit assignment).
    episode_steps : int
        Maximum steps per episode; terminated=True when reached.
    benchmark_kwargs : dict
        Extra kwargs forwarded verbatim to benchmark.run() on each step.
    benchmark_interval : int
        Run the benchmark every N steps instead of every step (§2.3).
        Default 1 preserves original behaviour; set higher for speed.
    storage : StorageBackend | None
        Optional storage backend for persisting benchmark results (§3.3).
    """

    metadata: Dict[str, Any] = {"render_modes": []}

    def __init__(
        self,
        controller: SchedulerController,
        monitor: Monitor,
        benchmark: BenchmarkRunner,
        registry: ParameterRegistry,
        watchdog: Optional[Watchdog] = None,
        action_mode: str = "discrete",
        episode_steps: int = 20,
        benchmark_kwargs: Optional[Dict[str, Any]] = None,
        benchmark_interval: int = 1,
        storage=None,
    ) -> None:
        super().__init__()
        self._controller = controller
        self._monitor = monitor
        self._benchmark = benchmark
        self._registry = registry
        self._watchdog = watchdog
        self._episode_steps = episode_steps
        self._benchmark_kwargs = benchmark_kwargs or {}
        self._benchmark_interval = max(1, benchmark_interval)
        self._storage = storage

        self._state_builder = StateBuilder(registry)
        self._action_mapper = ActionMapper(registry, mode=action_mode)
        self._reward_shaper = RewardShaper()

        self._step_count: int = 0
        self._last_reward: float = 0.0
        self._last_action: int | np.ndarray = 0
        self._last_benchmark_result = None
        self._baseline = None

        # Observation: system state + prev_action (1-hot or raw) + prev_reward (§2.2)
        n_params = len(registry.get_all())
        if action_mode == "discrete":
            self._extra_obs_dim = n_params * 2 + 1 + 1  # one-hot action + reward
        else:
            self._extra_obs_dim = n_params + 1  # continuous action + reward

        obs_dim = self._state_builder.obs_dim + self._extra_obs_dim

        # Gymnasium spaces (must be set before check_env)
        self.observation_space = spaces.Box(
            low=0.0,
            high=1.0,
            shape=(obs_dim,),
            dtype=np.float32,
        )
        self.action_space = self._action_mapper.action_space

    # ------------------------------------------------------------------
    # Gymnasium API
    # ------------------------------------------------------------------

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        super().reset(seed=seed)
        self._step_count = 0
        self._last_reward = 0.0
        self._last_action = 0
        self._last_benchmark_result = None

        self._check_watchdog()
        if self._baseline is None:
            self._baseline = self._controller.read_state()
        else:
            self._controller.restore_state(self._baseline)
        self._action_mapper.reset_state(self._controller.read_state())

        snapshot = self._monitor.read_snapshot()
        obs = self._build_obs(snapshot)
        return obs, {}

    def step(
        self, action: int | np.ndarray
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        return self._step(action)

    def measure_baseline(self):
        """Measure without writing, including when continuous zero is not a noop."""
        return self._step(None)

    def _step(self, action):
        self._check_watchdog()
        if self._baseline is None:
            raise RuntimeError("Call reset() before step()")
        self._step_count += 1
        rollback_triggered = False
        params_applied: Dict[str, Any] = {}

        # Decode action → parameter dict ({} for no-op)
        params = {} if action is None else self._action_mapper.decode(action)

        # Apply parameters — catch validation errors specifically (§7.1)
        if params:
            try:
                self._controller.apply_parameters(params)
                params_applied = params
            except ValidationError as exc:
                logger.debug("Validation error in apply_parameters: %s", exc)
                rollback_triggered = True
                self._action_mapper.reset_state(self._controller.read_state())
            except RecoveryError:
                raise
            except Exception as exc:
                # Unexpected errors should be logged at WARNING, not silently swallowed
                logger.warning(
                    "Unexpected error in apply_parameters (%s: %s) — marking rollback",
                    type(exc).__name__, exc,
                )
                rollback_triggered = True
                self._action_mapper.reset_state(self._controller.read_state())

        # Run benchmark to compute reward signal (§2.3: skip if not on interval)
        if self._step_count % self._benchmark_interval == 0 or self._last_benchmark_result is None:
            result = self._benchmark.run(**self._benchmark_kwargs)
            self._last_benchmark_result = result
            # Persist benchmark result if storage is wired (§3.3)
            if self._storage is not None:
                try:
                    self._storage.write_benchmark_result(
                        name=result.name,
                        workload_type=result.workload_type,
                        success=result.success,
                        score=result.score,
                        score_is_higher_better=result.score_is_higher_better,
                        metrics=result.metrics,
                        tag="training",
                    )
                except Exception:
                    logger.debug("Failed to persist benchmark result", exc_info=True)
        else:
            result = self._last_benchmark_result

        # A timeout is fatal: a completed benchmark must not revive the timer.
        self._check_watchdog()
        # Keep watchdog alive
        if self._watchdog is not None:
            self._watchdog.ping()

        # New observation after action
        snapshot = self._monitor.read_snapshot()
        reward = float(self._reward_shaper.shape(result, rollback_triggered))

        # Store for next step's augmented observation (§2.2)
        self._last_reward = reward
        self._last_action = 0 if action is None else action

        obs = self._build_obs(snapshot)

        terminated = self._step_count >= self._episode_steps
        truncated = False  # we don't truncate mid-episode; caller can wrap with TimeLimit

        info: Dict[str, Any] = {
            "benchmark": result,
            "params_applied": params_applied,
            "rollback_triggered": rollback_triggered,
            "step": self._step_count,
        }

        logger.debug(
            "step=%d action=%s reward=%.4f terminated=%s rollback=%s",
            self._step_count, action, reward, terminated, rollback_triggered,
        )

        return obs, reward, terminated, truncated, info

    def render(self) -> None:
        pass  # no rendering in M3; dashboard is M5

    def _check_watchdog(self) -> None:
        if self._watchdog is not None and self._watchdog.timed_out:
            raise RecoveryError("Watchdog timed out; stop training and restore baseline")

    def close(self) -> None:
        """Restore all values captured at the first reset; propagate failures."""
        if self._baseline is not None:
            self._controller.restore_state(self._baseline)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_obs(self, snapshot: SystemSnapshot) -> np.ndarray:
        """Build augmented observation: system state + prev_action + prev_reward (§2.2)."""
        base = self._state_builder.build(snapshot)
        extra = np.zeros(self._extra_obs_dim, dtype=np.float32)

        # Encode previous action
        if isinstance(self.action_space, spaces.Discrete):
            # One-hot for discrete
            idx = int(self._last_action)
            if 0 <= idx < self._extra_obs_dim - 1:
                extra[idx] = 1.0
        else:
            # Raw continuous action (clipped to [0,1] range)
            a = np.atleast_1d(np.asarray(self._last_action, dtype=np.float32))
            a = (a + 1.0) / 2.0  # map [-1,1] -> [0,1]
            n = min(len(a), self._extra_obs_dim - 1)
            extra[:n] = a[:n]

        # Last slot: previous reward (clipped to [0,1])
        extra[-1] = np.clip((self._last_reward + 1.0) / 2.0, 0.0, 1.0)

        return np.concatenate([base, extra])
