"""
Trainer — wraps stable-baselines3 PPO/SAC for the LinuxSchedulerEnv.

Usage
-----
    trainer = Trainer(env, algorithm="ppo", checkpoint_dir="data/checkpoints")
    result  = trainer.train(total_timesteps=50_000, checkpoint_freq=5_000)
    trainer.save("data/checkpoints/final_model")

    # Resume
    trainer = Trainer.load("data/checkpoints/final_model.zip", env, algorithm="ppo")
    action  = trainer.predict(obs)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import gymnasium

from stable_baselines3 import PPO, SAC
from stable_baselines3.common.monitor import Monitor as SB3Monitor
from stable_baselines3.common.evaluation import evaluate_policy

from core.checkpoint import SchedulerCheckpointCallback

logger = logging.getLogger(__name__)

_ALGORITHMS = {"ppo": PPO, "sac": SAC}


@dataclass
class TrainingResult:
    """Summary returned by Trainer.train()."""
    algorithm: str
    total_timesteps: int
    elapsed_sec: float
    mean_reward: float
    std_reward: float
    n_eval_episodes: int
    checkpoint_dir: Path


class Trainer:
    """Stable-Baselines3-backed trainer for LinuxSchedulerEnv.

    Parameters
    ----------
    env : gymnasium.Env
        The env to train on. Wrapped internally with SB3Monitor.
    algorithm : "ppo" | "sac"
        PPO works with Discrete actions (env default).
        SAC requires continuous actions (action_mode="continuous").
    policy : str
        SB3 policy class name. "MlpPolicy" for vector observations.
    checkpoint_dir : Path | str
        Directory for checkpoint files.
    tensorboard_log : str | None
        TensorBoard log dir. None = disabled.
    seed : int
    **algo_kwargs
        Extra keyword arguments forwarded to the SB3 algorithm constructor
        (e.g. n_steps=256 for PPO, learning_starts=100 for SAC).
    """

    def __init__(
        self,
        env: gymnasium.Env,
        algorithm: str = "ppo",
        policy: str = "MlpPolicy",
        checkpoint_dir: Path | str = Path("data/checkpoints"),
        tensorboard_log: Optional[str] = None,
        seed: int = 42,
        **algo_kwargs: Any,
    ) -> None:
        if algorithm not in _ALGORITHMS:
            raise ValueError(f"Unknown algorithm {algorithm!r}; choose from {list(_ALGORITHMS)}")

        self._algorithm_name = algorithm
        self._checkpoint_dir = Path(checkpoint_dir)
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Wrap with SB3Monitor for episode reward/length tracking
        self._wrapped_env = SB3Monitor(env)

        algo_cls = _ALGORITHMS[algorithm]
        self._model = algo_cls(
            policy,
            self._wrapped_env,
            seed=seed,
            tensorboard_log=tensorboard_log,
            verbose=0,
            **algo_kwargs,
        )
        logger.info("Trainer initialised: algorithm=%s policy=%s", algorithm, policy)

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def train(
        self,
        total_timesteps: int,
        checkpoint_freq: int = 1_000,
        eval_episodes: int = 5,
        progress_bar: bool = False,
    ) -> TrainingResult:
        """Train for `total_timesteps` steps, checkpoint every `checkpoint_freq`.

        Returns a TrainingResult with post-training evaluation stats.
        """
        t_start = time.monotonic()

        callback = SchedulerCheckpointCallback(
            save_freq=checkpoint_freq,
            save_path=self._checkpoint_dir,
            name_prefix=self._algorithm_name,
            algorithm=self._algorithm_name,
            training_config={
                "total_timesteps": total_timesteps,
                "checkpoint_freq": checkpoint_freq,
            },
            verbose=1,
        )

        logger.info("Training %s for %d timesteps...", self._algorithm_name, total_timesteps)
        self._model.learn(
            total_timesteps=total_timesteps,
            callback=callback,
            progress_bar=progress_bar,
            reset_num_timesteps=False,
        )

        elapsed = time.monotonic() - t_start
        eval_stats = self.evaluate(n_episodes=eval_episodes)

        result = TrainingResult(
            algorithm=self._algorithm_name,
            total_timesteps=total_timesteps,
            elapsed_sec=elapsed,
            mean_reward=eval_stats["mean_reward"],
            std_reward=eval_stats["std_reward"],
            n_eval_episodes=eval_episodes,
            checkpoint_dir=self._checkpoint_dir,
        )
        logger.info(
            "Training complete in %.1fs — mean_reward=%.4f ± %.4f",
            elapsed, result.mean_reward, result.std_reward,
        )
        return result

    def save(self, path: Path | str) -> None:
        """Save model weights to `path` (SB3 .zip format; extension added automatically)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._model.save(str(path))
        logger.info("Model saved → %s.zip", path)

    @classmethod
    def load(
        cls,
        path: Path | str,
        env: gymnasium.Env,
        algorithm: str = "ppo",
        checkpoint_dir: Path | str = Path("data/checkpoints"),
        **kwargs: Any,
    ) -> "Trainer":
        """Load a saved model and return a ready-to-use Trainer.

        Parameters
        ----------
        path : str | Path
            Path to the .zip model file (extension optional).
        env : gymnasium.Env
            Environment to bind to (must match original obs/action spaces).
        algorithm : str
            Must match the algorithm used during training.
        checkpoint_dir : Path | str
            Directory for future checkpoints (was hardcoded before — §7.2).
        """
        if algorithm not in _ALGORITHMS:
            raise ValueError("Unknown algorithm %r; choose from %s" % (algorithm, list(_ALGORITHMS)))

        instance = cls.__new__(cls)
        instance._algorithm_name = algorithm
        instance._checkpoint_dir = Path(checkpoint_dir)
        instance._wrapped_env = SB3Monitor(env)
        algo_cls = _ALGORITHMS[algorithm]
        instance._model = algo_cls.load(str(path), env=instance._wrapped_env, **kwargs)
        logger.info("Model loaded from %s", path)
        return instance

    def predict(self, obs: np.ndarray, deterministic: bool = True) -> int | np.ndarray:
        """Return an action for the given observation."""
        action, _ = self._model.predict(obs, deterministic=deterministic)
        return action

    def evaluate(self, n_episodes: int = 5) -> Dict[str, Any]:
        """Run `n_episodes` deterministic episodes and return reward stats."""
        mean_reward, std_reward = evaluate_policy(
            self._model,
            self._wrapped_env,
            n_eval_episodes=n_episodes,
            deterministic=True,
            warn=False,
        )
        return {
            "mean_reward": float(mean_reward),
            "std_reward": float(std_reward),
            "n_episodes": n_episodes,
        }

    # ------------------------------------------------------------------
    # Properties for introspection
    # ------------------------------------------------------------------

    @property
    def algorithm(self) -> str:
        return self._algorithm_name

    @property
    def num_timesteps(self) -> int:
        return self._model.num_timesteps
