"""
tests/test_trainer.py — M4 unit tests.

All tests use fake env components (no real sysctl, no real benchmark).
Training runs are kept extremely short (8-16 timesteps) via small
n_steps / learning_starts so tests finish in < 2s.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

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
)
from rl.env import LinuxSchedulerEnv
from core.trainer import Trainer, TrainingResult
from core.checkpoint import SchedulerCheckpointCallback


# ---------------------------------------------------------------------------
# Fakes (same pattern as test_rl_env.py)
# ---------------------------------------------------------------------------

class FakeBackend(SchedulerBackend):
    def __init__(self) -> None:
        self.state: Dict[str, str] = {
            "kernel.sched_min_granularity_ns": "3000000",
            "kernel.sched_wakeup_granularity_ns": "4000000",
        }
    def write(self, path: str, value: Any) -> None:
        self.state[path] = str(value)
    def read(self, path: str) -> Any:
        return self.state.get(path, "0")


class FakeMonitor:
    def read_snapshot(self) -> SystemSnapshot:
        return SystemSnapshot(
            timestamp=datetime.now(timezone.utc),
            cpu_util_pct=50.0, load_avg_1=1.0, load_avg_5=1.0,
            mem_util_pct=40.0, ctxt_switches_delta=10_000, runnable_procs=4,
        )


class FakeBenchmark(BenchmarkRunner):
    def __init__(self, score: float = 100.0) -> None:
        super().__init__(name="fake", workload_type="cpu")
        self._score = score
    def run(self, **kwargs) -> BenchmarkResult:
        return BenchmarkResult("fake", "cpu", True, self._score, True)


def _make_registry() -> ParameterRegistry:
    reg = ParameterRegistry()
    reg.register(ParameterMeta("sched_min_granularity_ns", int, 100_000, 100_000_000,
                               backend="sysctl", path="kernel.sched_min_granularity_ns"))
    reg.register(ParameterMeta("sched_wakeup_granularity_ns", int, 100_000, 100_000_000,
                               backend="sysctl", path="kernel.sched_wakeup_granularity_ns"))
    return reg


def _make_env(action_mode: str = "discrete", episode_steps: int = 4) -> LinuxSchedulerEnv:
    reg = _make_registry()
    backend = FakeBackend()
    controller = SchedulerController(reg, Validator(reg), Writer(reg, backend=backend),
                                     RollbackStack(), ProfileStore())
    return LinuxSchedulerEnv(
        controller=controller,
        monitor=FakeMonitor(),
        benchmark=FakeBenchmark(),
        registry=reg,
        episode_steps=episode_steps,
        action_mode=action_mode,
    )


# ---------------------------------------------------------------------------
# Trainer initialisation tests
# ---------------------------------------------------------------------------

class TestTrainerInit:
    def test_init_ppo_discrete(self):
        env = _make_env("discrete")
        trainer = Trainer(env, algorithm="ppo", n_steps=4, batch_size=4, n_epochs=1)
        assert trainer.algorithm == "ppo"
        assert trainer.num_timesteps == 0

    def test_init_sac_continuous(self):
        env = _make_env("continuous")
        trainer = Trainer(env, algorithm="sac", learning_starts=4, batch_size=4)
        assert trainer.algorithm == "sac"

    def test_unknown_algorithm_raises(self):
        env = _make_env()
        with pytest.raises(ValueError, match="Unknown algorithm"):
            Trainer(env, algorithm="a3c")


# ---------------------------------------------------------------------------
# Training tests
# ---------------------------------------------------------------------------

class TestTrainerTrain:
    def test_ppo_short_train_returns_result(self, tmp_path):
        env = _make_env("discrete")
        trainer = Trainer(env, algorithm="ppo",
                          checkpoint_dir=tmp_path,
                          n_steps=4, batch_size=4, n_epochs=1)
        result = trainer.train(total_timesteps=8, checkpoint_freq=4, eval_episodes=1)
        assert isinstance(result, TrainingResult)
        assert result.algorithm == "ppo"
        assert result.total_timesteps == 8
        assert result.elapsed_sec > 0
        assert result.n_eval_episodes == 1

    def test_sac_short_train_returns_result(self, tmp_path):
        env = _make_env("continuous")
        trainer = Trainer(env, algorithm="sac",
                          checkpoint_dir=tmp_path,
                          learning_starts=4, batch_size=4)
        result = trainer.train(total_timesteps=8, checkpoint_freq=4, eval_episodes=1)
        assert isinstance(result, TrainingResult)
        assert result.algorithm == "sac"

    def test_train_increments_num_timesteps(self, tmp_path):
        env = _make_env()
        trainer = Trainer(env, algorithm="ppo",
                          checkpoint_dir=tmp_path,
                          n_steps=4, batch_size=4, n_epochs=1)
        trainer.train(total_timesteps=8, checkpoint_freq=100, eval_episodes=1)
        assert trainer.num_timesteps >= 8


# ---------------------------------------------------------------------------
# Predict tests
# ---------------------------------------------------------------------------

class TestTrainerPredict:
    def test_predict_returns_valid_action(self, tmp_path):
        env = _make_env("discrete")
        trainer = Trainer(env, algorithm="ppo",
                          checkpoint_dir=tmp_path,
                          n_steps=4, batch_size=4, n_epochs=1)
        trainer.train(total_timesteps=8, checkpoint_freq=100, eval_episodes=1)
        obs, _ = env.reset()
        action = trainer.predict(obs)
        assert env.action_space.contains(int(action))


# ---------------------------------------------------------------------------
# Save / Load tests
# ---------------------------------------------------------------------------

class TestTrainerSaveLoad:
    def test_save_creates_zip(self, tmp_path):
        env = _make_env()
        trainer = Trainer(env, algorithm="ppo",
                          checkpoint_dir=tmp_path,
                          n_steps=4, batch_size=4, n_epochs=1)
        trainer.train(total_timesteps=8, checkpoint_freq=100, eval_episodes=1)
        save_path = tmp_path / "my_model"
        trainer.save(save_path)
        assert (tmp_path / "my_model.zip").exists()

    def test_load_and_predict(self, tmp_path):
        env = _make_env()
        trainer = Trainer(env, algorithm="ppo",
                          checkpoint_dir=tmp_path,
                          n_steps=4, batch_size=4, n_epochs=1)
        trainer.train(total_timesteps=8, checkpoint_freq=100, eval_episodes=1)
        save_path = tmp_path / "test_model"
        trainer.save(save_path)

        env2 = _make_env()
        loaded = Trainer.load(save_path, env2, algorithm="ppo")
        obs, _ = env2.reset()
        action = loaded.predict(obs)
        assert env2.action_space.contains(int(action))


# ---------------------------------------------------------------------------
# Evaluate tests
# ---------------------------------------------------------------------------

class TestTrainerEvaluate:
    def test_evaluate_returns_expected_keys(self, tmp_path):
        env = _make_env()
        trainer = Trainer(env, algorithm="ppo",
                          checkpoint_dir=tmp_path,
                          n_steps=4, batch_size=4, n_epochs=1)
        trainer.train(total_timesteps=8, checkpoint_freq=100, eval_episodes=1)
        stats = trainer.evaluate(n_episodes=2)
        assert "mean_reward" in stats
        assert "std_reward" in stats
        assert stats["n_episodes"] == 2


# ---------------------------------------------------------------------------
# Checkpoint callback tests
# ---------------------------------------------------------------------------

class TestCheckpointCallback:
    def _make_trainer_and_train(self, tmp_path, checkpoint_freq=4):
        env = _make_env()
        trainer = Trainer(env, algorithm="ppo",
                          checkpoint_dir=tmp_path,
                          n_steps=4, batch_size=4, n_epochs=1)
        trainer.train(total_timesteps=8, checkpoint_freq=checkpoint_freq, eval_episodes=1)
        return trainer

    def test_checkpoint_zip_files_created(self, tmp_path):
        self._make_trainer_and_train(tmp_path, checkpoint_freq=4)
        zips = list(tmp_path.glob("ppo_*_steps.zip"))
        assert len(zips) >= 1

    def test_checkpoint_metadata_json_created(self, tmp_path):
        self._make_trainer_and_train(tmp_path, checkpoint_freq=4)
        metas = list(tmp_path.glob("ppo_*_steps_meta.json"))
        assert len(metas) >= 1

    def test_metadata_json_has_expected_fields(self, tmp_path):
        self._make_trainer_and_train(tmp_path, checkpoint_freq=4)
        meta_file = sorted(tmp_path.glob("ppo_*_steps_meta.json"))[0]
        with open(meta_file) as f:
            data = json.load(f)
        for key in ("num_timesteps", "algorithm", "timestamp", "training_config", "n_episodes"):
            assert key in data, f"Missing key: {key}"
        assert data["algorithm"] == "ppo"
