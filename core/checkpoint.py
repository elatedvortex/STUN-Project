"""
SchedulerCheckpointCallback — saves model + JSON metadata at regular intervals.

Files written per checkpoint:
  {name_prefix}_{n_timesteps}_steps.zip        — SB3 model weights
  {name_prefix}_{n_timesteps}_steps_meta.json  — training metadata
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback

logger = logging.getLogger(__name__)


class SchedulerCheckpointCallback(BaseCallback):
    """SB3 callback: checkpoint model + metadata every `save_freq` env steps.

    Parameters
    ----------
    save_freq : int
        Save every N environment steps.
    save_path : Path | str
        Directory to write checkpoints into (created if absent).
    name_prefix : str
        File prefix, e.g. "ppo" → "ppo_1000_steps.zip".
    algorithm : str
        Algorithm name embedded in metadata JSON.
    training_config : dict | None
        Arbitrary key/value config to embed in every metadata JSON.
    verbose : int
        0 = silent, 1 = log on each save.
    """

    def __init__(
        self,
        save_freq: int,
        save_path: Path | str,
        name_prefix: str = "model",
        algorithm: str = "ppo",
        training_config: Optional[Dict[str, Any]] = None,
        verbose: int = 0,
    ) -> None:
        super().__init__(verbose)
        self._save_freq = save_freq
        self._save_path = Path(save_path)
        self._name_prefix = name_prefix
        self._algorithm = algorithm
        self._training_config = training_config or {}
        self._episode_rewards: List[float] = []
        self._current_ep_reward: float = 0.0
        self._save_path.mkdir(parents=True, exist_ok=True)

    def _on_step(self) -> bool:
        # Accumulate per-episode rewards from VecEnv step locals
        rewards = np.atleast_1d(self.locals.get("rewards", np.zeros(1)))
        dones = np.atleast_1d(self.locals.get("dones", np.zeros(1, dtype=bool)))
        for reward, done in zip(rewards, dones):
            self._current_ep_reward += float(reward)
            if done:
                self._episode_rewards.append(self._current_ep_reward)
                self._current_ep_reward = 0.0

        if self.n_calls % self._save_freq == 0:
            self._save_checkpoint()
        return True

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def episode_rewards(self) -> List[float]:
        return list(self._episode_rewards)

    def _save_checkpoint(self) -> None:
        stem = f"{self._name_prefix}_{self.num_timesteps}_steps"
        model_path = self._save_path / stem
        self.model.save(str(model_path))

        recent = self._episode_rewards[-50:]
        meta: Dict[str, Any] = {
            "num_timesteps": self.num_timesteps,
            "algorithm": self._algorithm,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "training_config": self._training_config,
            "n_episodes": len(self._episode_rewards),
            "mean_reward": float(np.mean(recent)) if recent else None,
            "std_reward": float(np.std(recent)) if recent else None,
        }
        meta_path = self._save_path / f"{stem}_meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        if self.verbose >= 1:
            logger.info("Checkpoint saved → %s  (episodes=%d)", model_path, len(self._episode_rewards))
