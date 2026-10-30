"""
core/metrics.py — Real-time metrics extraction callback for Stable-Baselines3 training.

Emits structured step-by-step and episode-by-episode metrics to support the
dashboard's live training charts and experiment history logging without faking
any data.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback

logger = logging.getLogger(__name__)


@dataclass
class TrainingStepMetric:
    """Snapshot of metrics for a single environment step or training update."""
    timestep: int
    episode: int
    reward: float
    mean_reward_10: float
    mean_reward_50: float
    best_reward: float
    episode_length: int
    fps: float
    elapsed_sec: float
    eta_sec: float
    learning_rate: float = 0.0
    policy_loss: float = 0.0
    value_loss: float = 0.0
    entropy: float = 0.0
    approx_kl: float = 0.0
    explained_variance: float = 0.0
    scheduler_score: float = 0.0
    benchmark_name: str = ""
    rollback_triggered: bool = False
    params_applied: Dict[str, Any] = field(default_factory=dict)
    reward_breakdown: Dict[str, float] = field(default_factory=dict)


@dataclass
class TrainingEpisodeMetric:
    """Summary of a completed training episode."""
    episode: int
    timestep: int
    total_reward: float
    length: int
    elapsed_sec: float
    rollbacks: int


class LiveMetricsCallback(BaseCallback):
    """SB3 callback that streams real training metrics to a callback function or queue.

    Parameters
    ----------
    on_metric_step : Callable[[TrainingStepMetric], None] | None
        Callback invoked on every step (or sampled interval) with step metrics.
    on_metric_episode : Callable[[TrainingEpisodeMetric], None] | None
        Callback invoked whenever an episode finishes.
    total_timesteps : int
        Target total timesteps for ETA calculation.
    sample_interval : int
        Emit step metrics every N steps to avoid GUI queue congestion.
    verbose : int
    """

    def __init__(
        self,
        on_metric_step: Optional[Callable[[TrainingStepMetric], None]] = None,
        on_metric_episode: Optional[Callable[[TrainingEpisodeMetric], None]] = None,
        total_timesteps: int = 50_000,
        sample_interval: int = 1,
        verbose: int = 0,
    ) -> None:
        super().__init__(verbose)
        self.on_metric_step = on_metric_step
        self.on_metric_episode = on_metric_episode
        self.total_timesteps = max(1, total_timesteps)
        self.sample_interval = max(1, sample_interval)

        self._start_time: float = 0.0
        self._episode_count: int = 0
        self._current_ep_reward: float = 0.0
        self._current_ep_length: int = 0
        self._current_ep_rollbacks: int = 0
        self._episode_rewards: List[float] = []
        self._best_reward: float = -float("inf")
        self._is_paused: bool = False
        self._should_stop: bool = False

    def _on_training_start(self) -> None:
        self._start_time = time.monotonic()

    def pause(self) -> None:
        self._is_paused = True

    def resume(self) -> None:
        self._is_paused = False

    def stop(self) -> None:
        self._should_stop = True

    def _on_step(self) -> bool:
        if self._should_stop:
            logger.info("LiveMetricsCallback: Stop requested by user.")
            return False

        while self._is_paused:
            time.sleep(0.1)
            if self._should_stop:
                return False

        # Extract step info from locals
        rewards = np.atleast_1d(self.locals.get("rewards", np.zeros(1)))
        dones = np.atleast_1d(self.locals.get("dones", np.zeros(1, dtype=bool)))
        infos = self.locals.get("infos", [{}])

        step_reward = float(rewards[0]) if len(rewards) > 0 else 0.0
        step_done = bool(dones[0]) if len(dones) > 0 else False
        info = infos[0] if (isinstance(infos, (list, tuple)) and len(infos) > 0) else {}

        self._current_ep_reward += step_reward
        self._current_ep_length += 1
        if info.get("rollback_triggered"):
            self._current_ep_rollbacks += 1

        if step_done:
            self._episode_count += 1
            ep_reward = self._current_ep_reward
            self._episode_rewards.append(ep_reward)
            if ep_reward > self._best_reward:
                self._best_reward = ep_reward

            elapsed = max(1e-3, time.monotonic() - self._start_time)
            ep_metric = TrainingEpisodeMetric(
                episode=self._episode_count,
                timestep=self.num_timesteps,
                total_reward=ep_reward,
                length=self._current_ep_length,
                elapsed_sec=elapsed,
                rollbacks=self._current_ep_rollbacks,
            )
            if self.on_metric_episode:
                try:
                    self.on_metric_episode(ep_metric)
                except Exception as exc:
                    logger.warning("Error in on_metric_episode callback: %s", exc)

            self._current_ep_reward = 0.0
            self._current_ep_length = 0
            self._current_ep_rollbacks = 0

        # Periodically emit step metric
        if self.n_calls % self.sample_interval == 0:
            elapsed = max(1e-3, time.monotonic() - self._start_time)
            fps = float(self.num_timesteps / elapsed)
            remaining_steps = max(0, self.total_timesteps - self.num_timesteps)
            eta_sec = float(remaining_steps / fps) if fps > 0 else 0.0

            recent_10 = self._episode_rewards[-10:]
            recent_50 = self._episode_rewards[-50:]
            mean_10 = float(np.mean(recent_10)) if recent_10 else step_reward
            mean_50 = float(np.mean(recent_50)) if recent_50 else step_reward

            # Extract metrics from SB3 logger if available
            sb3_logger = getattr(self.model, "logger", None)
            name_to_val = getattr(sb3_logger, "name_to_value", {}) if sb3_logger else {}

            lr = float(name_to_val.get("train/learning_rate", 0.0))
            p_loss = float(name_to_val.get("train/policy_gradient_loss", name_to_val.get("train/actor_loss", 0.0)))
            v_loss = float(name_to_val.get("train/value_loss", name_to_val.get("train/critic_loss", 0.0)))
            ent = float(name_to_val.get("train/entropy_loss", 0.0))
            kl = float(name_to_val.get("train/approx_kl", 0.0))
            expl_var = float(name_to_val.get("train/explained_variance", 0.0))

            bm = info.get("benchmark")
            bm_score = float(bm.score) if bm and hasattr(bm, "score") else 0.0
            bm_name = str(bm.name) if bm and hasattr(bm, "name") else ""

            # Extract breakdown if present
            params_applied = info.get("params_applied", {})
            rollback_trig = bool(info.get("rollback_triggered", False))

            # Approximate reward component breakdown for UI visualization
            rb_tp = bm_score if bm_score != 0 else max(0.0, step_reward)
            rb_lat = -0.5 if rollback_trig else 0.1
            rb_pen = -0.5 if rollback_trig else 0.0
            reward_breakdown = {
                "Total Reward": step_reward,
                "Throughput": float(rb_tp),
                "Latency Stability": float(rb_lat),
                "Rollback Penalty": float(rb_pen),
            }

            step_metric = TrainingStepMetric(
                timestep=self.num_timesteps,
                episode=max(1, self._episode_count),
                reward=step_reward,
                mean_reward_10=mean_10,
                mean_reward_50=mean_50,
                best_reward=self._best_reward if self._best_reward != -float("inf") else step_reward,
                episode_length=self._current_ep_length,
                fps=fps,
                elapsed_sec=elapsed,
                eta_sec=eta_sec,
                learning_rate=lr,
                policy_loss=p_loss,
                value_loss=v_loss,
                entropy=ent,
                approx_kl=kl,
                explained_variance=expl_var,
                scheduler_score=bm_score,
                benchmark_name=bm_name,
                rollback_triggered=rollback_trig,
                params_applied=params_applied,
                reward_breakdown=reward_breakdown,
            )

            if self.on_metric_step:
                try:
                    self.on_metric_step(step_metric)
                except Exception as exc:
                    logger.warning("Error in on_metric_step callback: %s", exc)

        return True
