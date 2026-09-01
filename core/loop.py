"""
EpisodeRunner — thin orchestrator that ties LinuxSchedulerEnv + an agent
together for a single episode.

Owns the Watchdog thread lifecycle (start before episode, stop after) so
the Env itself stays thread-unaware and unit-testable.

This is the shell M4's training loop will drive in a loop; for M3 it's
used only by scripts/run_rl.py to demonstrate the full pipeline.

Agent protocol
--------------
The runner expects any object with a predict(obs) method that returns
an action compatible with env.action_space:

  class MyAgent:
      def predict(self, obs: np.ndarray) -> int | np.ndarray: ...

A RandomAgent is provided here for dry-run / smoke-test use.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Protocol

import numpy as np

from rl.env import LinuxSchedulerEnv
from safety.watchdog import Watchdog

logger = logging.getLogger(__name__)


class Agent(Protocol):
    """Minimal agent interface — any object with predict() qualifies."""
    def predict(self, obs: np.ndarray) -> int | np.ndarray: ...


class RandomAgent:
    """Samples uniformly from the action space — useful for dry-runs."""
    def __init__(self, action_space) -> None:
        self._action_space = action_space

    def predict(self, obs: np.ndarray) -> int | np.ndarray:
        return self._action_space.sample()


class EpisodeRunner:
    """Runs one episode of LinuxSchedulerEnv with a given agent.

    Parameters
    ----------
    env : LinuxSchedulerEnv
    agent : Agent
        Any object with a predict(obs) method.
    watchdog : Watchdog | None
        If provided, the runner starts it before reset() and stops it
        after the episode ends.
    """

    def __init__(
        self,
        env: LinuxSchedulerEnv,
        agent: Agent,
        watchdog: Watchdog | None = None,
    ) -> None:
        self._env = env
        self._agent = agent
        self._watchdog = watchdog

    def run_episode(self) -> Dict[str, Any]:
        """Run one full episode and return episode statistics.

        Returns
        -------
        dict with keys:
          total_reward   : float
          steps          : int
          mean_reward    : float
          rollbacks      : int
          elapsed_sec    : float
        """
        t_start = time.monotonic()

        if self._watchdog is not None:
            self._watchdog.start()

        obs, _ = self._env.reset()

        total_reward = 0.0
        steps = 0
        rollbacks = 0
        terminated = False
        truncated = False

        while not (terminated or truncated):
            action = self._agent.predict(obs)
            obs, reward, terminated, truncated, info = self._env.step(action)
            total_reward += reward
            steps += 1
            if info.get("rollback_triggered"):
                rollbacks += 1
            logger.debug(
                "step=%d reward=%.4f rollback=%s",
                steps, reward, info.get("rollback_triggered"),
            )

        if self._watchdog is not None:
            self._watchdog.stop()

        elapsed = time.monotonic() - t_start
        stats = {
            "total_reward": total_reward,
            "steps": steps,
            "mean_reward": total_reward / max(steps, 1),
            "rollbacks": rollbacks,
            "elapsed_sec": elapsed,
        }
        logger.info("Episode done: %s", stats)
        return stats
