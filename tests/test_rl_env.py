"""
tests/test_rl_env.py — M3 unit tests.

All tests run against fake/stub components:
  - FakeMonitor      : returns a hardcoded SystemSnapshot
  - FakeBenchmark    : returns a hardcoded BenchmarkResult
  - FakeBackend      : in-memory dict (reuses the pattern from test_scheduler.py)

No root privileges, no real kernel, no subprocess calls.
Requires: numpy, gymnasium (see requirements.txt).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import numpy as np
import pytest

from monitor.types import SystemSnapshot
from benchmarks.base import BenchmarkRunner
from benchmarks.types import BenchmarkResult
from scheduler import (
    ParameterMeta,
    ParameterRegistry,
    Validator,
    Writer,
    RollbackStack,
    ProfileStore,
    SchedulerController,
    SchedulerBackend,
    ValidationError,
)
from rl.state import StateBuilder
from rl.action import ActionMapper
from rl.reward import RewardShaper
from rl.env import LinuxSchedulerEnv


# ---------------------------------------------------------------------------
# Fakes / helpers
# ---------------------------------------------------------------------------

def _make_snapshot(**overrides) -> SystemSnapshot:
    """Return a minimal SystemSnapshot with sensible defaults."""
    defaults = dict(
        timestamp=datetime.now(timezone.utc),
        cpu_util_pct=50.0,
        load_avg_1=1.0,
        load_avg_5=1.0,
        load_avg_15=1.0,
        mem_util_pct=40.0,
        ctxt_switches_delta=10_000,
        runnable_procs=4,
        total_procs=200,
        sched_params={
            "kernel.sched_min_granularity_ns": 3_000_000.0,
            "kernel.sched_wakeup_granularity_ns": 4_000_000.0,
        },
    )
    defaults.update(overrides)
    return SystemSnapshot(**defaults)


class FakeMonitor:
    """Returns a fixed snapshot on every read_snapshot() call."""
    def __init__(self, snapshot: Optional[SystemSnapshot] = None) -> None:
        self._snapshot = snapshot or _make_snapshot()

    def read_snapshot(self) -> SystemSnapshot:
        return self._snapshot


class FakeBenchmark(BenchmarkRunner):
    def __init__(
        self,
        score: float = 100.0,
        success: bool = True,
        higher_is_better: bool = True,
    ) -> None:
        super().__init__(name="fake", workload_type="cpu")
        self._result = BenchmarkResult(
            name="fake",
            workload_type="cpu",
            success=success,
            score=score,
            score_is_higher_better=higher_is_better,
            metrics={"ops": score},
        )
        self.call_count = 0

    def run(self, **kwargs) -> BenchmarkResult:
        self.call_count += 1
        return self._result


class FakeBackend(SchedulerBackend):
    def __init__(self) -> None:
        self.state: Dict[str, str] = {}

    def write(self, path: str, value: Any) -> None:
        self.state[path] = str(value)

    def read(self, path: str) -> Any:
        return self.state.get(path, "0")


def _make_registry() -> ParameterRegistry:
    reg = ParameterRegistry()
    reg.register(ParameterMeta(
        name="sched_min_granularity_ns",
        type=int,
        min_value=100_000,
        max_value=100_000_000,
        backend="sysctl",
        path="kernel.sched_min_granularity_ns",
    ))
    reg.register(ParameterMeta(
        name="sched_wakeup_granularity_ns",
        type=int,
        min_value=100_000,
        max_value=100_000_000,
        backend="sysctl",
        path="kernel.sched_wakeup_granularity_ns",
    ))
    return reg


def _make_controller(registry: ParameterRegistry, backend: FakeBackend) -> SchedulerController:
    validator = Validator(registry)
    writer = Writer(registry, backend=backend)
    rollback_stack = RollbackStack()
    profile_store = ProfileStore()
    # Seed backend with initial state so rollback has something to read
    backend.state["kernel.sched_min_granularity_ns"] = "3000000"
    backend.state["kernel.sched_wakeup_granularity_ns"] = "4000000"
    return SchedulerController(registry, validator, writer, rollback_stack, profile_store)


def _make_env(
    registry=None,
    backend=None,
    monitor=None,
    benchmark=None,
    episode_steps=5,
    action_mode="discrete",
) -> tuple[LinuxSchedulerEnv, FakeBackend]:
    registry = registry or _make_registry()
    backend = backend or FakeBackend()
    controller = _make_controller(registry, backend)
    monitor = monitor or FakeMonitor()
    benchmark = benchmark or FakeBenchmark()
    env = LinuxSchedulerEnv(
        controller=controller,
        monitor=monitor,
        benchmark=benchmark,
        registry=registry,
        episode_steps=episode_steps,
        action_mode=action_mode,
    )
    return env, backend


# ---------------------------------------------------------------------------
# StateBuilder tests
# ---------------------------------------------------------------------------

class TestStateBuilder:
    def test_sysctl_paths_populate_parameter_observations(self):
        builder = StateBuilder(_make_registry())
        obs = builder.build(_make_snapshot())
        assert obs[6] == pytest.approx(0.03)
        assert obs[7] == pytest.approx(0.04)

    def test_profile_distance_accepts_sysctl_paths(self):
        from workload.context import _profile_distance
        distance = _profile_distance(
            {"kernel.sched_min_granularity_ns": 100_000},
            {"kernel.sched_min_granularity_ns": 100_000_000},
            _make_registry(),
        )
        assert distance == pytest.approx(0.5)

    def test_state_builder_shape(self):
        reg = _make_registry()
        sb = StateBuilder(reg)
        snap = _make_snapshot()
        obs = sb.build(snap)
        assert obs.shape == (sb.obs_dim,)
        assert obs.dtype == np.float32

    def test_state_builder_obs_dim(self):
        reg = _make_registry()
        sb = StateBuilder(reg)
        # 6 fixed fields + 2 registered params
        assert sb.obs_dim == 8

    def test_state_builder_none_fields_become_zero(self):
        reg = _make_registry()
        sb = StateBuilder(reg)
        # All optional fields set to None
        snap = SystemSnapshot(
            timestamp=datetime.now(timezone.utc),
            cpu_util_pct=None,
            load_avg_1=None,
            mem_util_pct=None,
            ctxt_switches_delta=None,
            runnable_procs=None,
        )
        obs = sb.build(snap)
        # fixed slots should all be 0.0 (no crash, no NaN)
        assert not np.any(np.isnan(obs))
        np.testing.assert_array_equal(obs[:6], 0.0)

    def test_state_builder_normalisation_in_range(self):
        reg = _make_registry()
        sb = StateBuilder(reg)
        snap = _make_snapshot(cpu_util_pct=100.0, mem_util_pct=100.0)
        obs = sb.build(snap)
        assert np.all(obs >= 0.0), "obs has values below 0"
        assert np.all(obs <= 1.0), "obs has values above 1"


# ---------------------------------------------------------------------------
# ActionMapper tests
# ---------------------------------------------------------------------------

class TestActionMapper:
    def test_action_mapper_discrete_noop(self):
        reg = _make_registry()
        am = ActionMapper(reg, mode="discrete")
        result = am.decode(0)
        assert result == {}

    def test_action_mapper_discrete_increment(self):
        reg = _make_registry()
        am = ActionMapper(reg, mode="discrete", n_steps=10)
        am.reset_state()
        # Action 1 → increment first param
        result = am.decode(1)
        assert len(result) == 1
        name = list(result.keys())[0]
        assert name == "sched_min_granularity_ns"
        # Should be midpoint + one step
        meta = reg.get(name)
        step = (meta.max_value - meta.min_value) / 10
        mid = (meta.min_value + meta.max_value) / 2.0
        assert result[name] == pytest.approx(int(mid + step), abs=1)

    def test_action_mapper_discrete_decrement(self):
        reg = _make_registry()
        am = ActionMapper(reg, mode="discrete", n_steps=10)
        n_params = len(reg.get_all())
        # Action n_params+1 → decrement first param
        result = am.decode(n_params + 1)
        assert len(result) == 1
        name = list(result.keys())[0]
        meta = reg.get(name)
        step = (meta.max_value - meta.min_value) / 10
        mid = (meta.min_value + meta.max_value) / 2.0
        assert result[name] == pytest.approx(int(mid - step), abs=1)

    def test_action_mapper_clips_to_bounds(self):
        reg = _make_registry()
        am = ActionMapper(reg, mode="discrete", n_steps=1)
        # Spam increment well past max_value
        for _ in range(200):
            am.decode(1)
        result = am.decode(1)
        meta = reg.get("sched_min_granularity_ns")
        assert result["sched_min_granularity_ns"] <= meta.max_value

    def test_action_mapper_continuous_shape(self):
        reg = _make_registry()
        am = ActionMapper(reg, mode="continuous")
        action = np.array([0.5, -0.5], dtype=np.float32)
        result = am.decode(action)
        assert set(result.keys()) == {"sched_min_granularity_ns", "sched_wakeup_granularity_ns"}

    def test_action_space_discrete(self):
        reg = _make_registry()
        am = ActionMapper(reg, mode="discrete")
        # 2 params → 2*2+1 = 5
        assert am.action_space.n == 5

    def test_action_space_continuous(self):
        reg = _make_registry()
        am = ActionMapper(reg, mode="continuous")
        assert am.action_space.shape == (2,)


# ---------------------------------------------------------------------------
# RewardShaper tests
# ---------------------------------------------------------------------------

class TestRewardShaper:
    def test_reward_shaper_failed_benchmark(self):
        rs = RewardShaper()
        result = BenchmarkResult("fake", "cpu", False, 0.0, True)
        r = rs.shape(result, rollback_triggered=False)
        assert r == pytest.approx(-1.0)

    def test_reward_shaper_stability_bonus(self):
        rs = RewardShaper(lambda_stability=0.1)
        result = BenchmarkResult("fake", "cpu", True, 100.0, True)
        # First call initialises EMA — normalised score = 0.0, +stability bonus
        r = rs.shape(result, rollback_triggered=False)
        assert r == pytest.approx(0.0 + 0.1, abs=1e-6)

    def test_reward_shaper_rollback_penalty(self):
        rs = RewardShaper(lambda_stability=0.1, lambda_penalty=0.5)
        result = BenchmarkResult("fake", "cpu", True, 100.0, True)
        r_no_rb = rs.shape(result, rollback_triggered=False)
        rs2 = RewardShaper(lambda_stability=0.1, lambda_penalty=0.5)
        r_rb = rs2.shape(result, rollback_triggered=True)
        assert r_rb < r_no_rb

    def test_reward_shaper_ema_tracks_improvement(self):
        rs = RewardShaper(ema_alpha=0.5)
        # Two scores: 100 then 200 (big improvement)
        r1 = BenchmarkResult("f", "cpu", True, 100.0, True)
        r2 = BenchmarkResult("f", "cpu", True, 200.0, True)
        rs.shape(r1)  # initialise
        reward = rs.shape(r2)  # should be positive (above baseline)
        assert reward > 0

    def test_reward_shaper_lower_is_better_inversion(self):
        rs = RewardShaper()
        # First call with lower-is-better score of 5.0
        r1 = BenchmarkResult("hack", "mixed", True, 5.0, False)
        rs.shape(r1)  # initialise EMA at -5.0
        # Second call with better (lower) score
        r2 = BenchmarkResult("hack", "mixed", True, 3.0, False)
        reward = rs.shape(r2)  # -3 > -5 → positive improvement
        assert reward > 0


# ---------------------------------------------------------------------------
# LinuxSchedulerEnv tests
# ---------------------------------------------------------------------------

class TestLinuxSchedulerEnv:
    def test_multiple_actions_reset_and_close_restore_original_baseline(self):
        env, backend = _make_env(episode_steps=10)
        original = dict(backend.state)
        env.reset()
        env.step(1)
        env.step(2)
        env.step(1)
        assert backend.state != original
        env.reset()
        assert backend.state == original
        env.step(2)
        env.close()
        assert backend.state == original

    def test_first_increment_uses_kernel_value(self):
        env, backend = _make_env()
        env.reset()
        env.step(1)
        assert int(backend.state["kernel.sched_min_granularity_ns"]) == 3_000_000 + 4_995_000

    def test_reset_propagates_restore_failure(self):
        env, _ = _make_env()
        env.reset()
        env._controller.restore_state = MagicMock(side_effect=RuntimeError("restore failed"))
        with pytest.raises(RuntimeError, match="restore failed"):
            env.reset()

    def test_timeout_aborts_before_and_after_benchmark(self):
        from safety.watchdog import Watchdog
        from scheduler.exceptions import RecoveryError
        env, _ = _make_env()
        watchdog = Watchdog(lambda: None)
        env._watchdog = watchdog
        env.reset()

        def timeout(**kwargs):
            watchdog._timed_out = True
            return BenchmarkResult("fake", "cpu", True, 1.0, True)

        env._benchmark.run = timeout
        with pytest.raises(RecoveryError, match="Watchdog"):
            env.step(1)
        with pytest.raises(RecoveryError, match="Watchdog"):
            env.step(1)

    def test_env_reset_returns_correct_obs_shape(self):
        env, _ = _make_env()
        obs, info = env.reset()
        assert obs.shape == env.observation_space.shape
        assert obs.dtype == np.float32
        assert isinstance(info, dict)

    def test_env_step_noop_no_crash(self):
        env, _ = _make_env()
        env.reset()
        obs, reward, terminated, truncated, info = env.step(0)
        assert obs.shape == env.observation_space.shape
        assert isinstance(reward, float)
        assert isinstance(terminated, bool)
        assert truncated is False
        assert isinstance(info, dict)

    def test_env_step_applies_params_to_backend(self):
        env, backend = _make_env(episode_steps=10)
        env.reset()
        # Action 1 = increment first param; apply_parameters should write to backend
        env.step(1)
        # Backend should have been written to (value changed from initial seed)
        assert "kernel.sched_min_granularity_ns" in backend.state

    def test_env_terminates_after_episode_steps(self):
        env, _ = _make_env(episode_steps=3)
        env.reset()
        for _ in range(2):
            _, _, terminated, _, _ = env.step(0)
            assert not terminated
        _, _, terminated, _, _ = env.step(0)
        assert terminated

    def test_env_info_contains_expected_keys(self):
        env, _ = _make_env()
        env.reset()
        _, _, _, _, info = env.step(0)
        assert "benchmark" in info
        assert "params_applied" in info
        assert "rollback_triggered" in info
        assert "step" in info

    def test_env_validation_error_sets_rollback_flag(self):
        """An action that decodes to an out-of-bounds value should set
        rollback_triggered=True in info without crashing the env."""
        reg = _make_registry()
        backend = FakeBackend()
        backend.state["kernel.sched_min_granularity_ns"] = "3000000"
        backend.state["kernel.sched_wakeup_granularity_ns"] = "4000000"
        validator = Validator(reg)
        writer = Writer(reg, backend=backend)
        rollback_stack = RollbackStack()
        profile_store = ProfileStore()
        controller = SchedulerController(reg, validator, writer, rollback_stack, profile_store)

        # Monkey-patch apply_parameters to always raise ValidationError
        controller.apply_parameters = MagicMock(side_effect=ValidationError("forced error"))

        monitor = FakeMonitor()
        benchmark = FakeBenchmark()
        env = LinuxSchedulerEnv(
            controller=controller,
            monitor=monitor,
            benchmark=benchmark,
            registry=reg,
            episode_steps=5,
        )
        env.reset()
        _, _, _, _, info = env.step(1)  # non-noop action
        assert info["rollback_triggered"] is True

    def test_env_benchmark_called_every_step(self):
        bench = FakeBenchmark()
        env, _ = _make_env(benchmark=bench, episode_steps=4)
        env.reset()
        for _ in range(4):
            env.step(0)
        assert bench.call_count == 4

    def test_check_env(self):
        """gymnasium.utils.env_checker.check_env must pass."""
        from gymnasium.utils.env_checker import check_env
        env, _ = _make_env(episode_steps=3)
        check_env(env, skip_render_check=True)
