"""
RewardShaper — converts a BenchmarkResult into a scalar reward signal.

reward = normalised_score  ∈ [-1, 1]
       + λ_stability * stability_bonus   (if no rollback triggered)
       - λ_penalty  * rollback_penalty   (if rollback triggered)

Normalised score is computed relative to a rolling EMA baseline of recent
scores so the signal stays meaningful as the agent improves — without this,
a mediocre score looks great early on but the reward scale drifts.

The EMA is intentionally NOT reset between episodes: it tracks the long-term
average performance, not within-episode performance. This is a deliberate
design choice — if you want per-episode normalisation, set ema_alpha=1.0 and
call reset() at episode start.

Higher is always better for the shaper internally. For benchmarks where lower
is better (hackbench, cyclictest), the score is negated before normalisation.
"""

from __future__ import annotations

from benchmarks.types import BenchmarkResult


class RewardShaper:
    def __init__(
        self,
        lambda_stability: float = 0.1,
        lambda_penalty: float = 0.5,
        ema_alpha: float = 0.05,
        warmup_steps: int = 3,
    ) -> None:
        self._lambda_stability = lambda_stability
        self._lambda_penalty = lambda_penalty
        self._ema_alpha = ema_alpha
        self._warmup_steps = warmup_steps
        self._ema_baseline: float | None = None
        self._sample_count: int = 0

    def shape(self, result: BenchmarkResult, rollback_triggered: bool = False) -> float:
        """Shape a BenchmarkResult into a scalar reward.

        Parameters
        ----------
        result : BenchmarkResult
            Output from any BenchmarkRunner.run() call.
        rollback_triggered : bool
            True if the controller rolled back (validation error or watchdog).

        Returns
        -------
        float
            Reward in approximately [-1.6, 1.1] (unbounded in theory, but
            practically clipped by design).
        """
        # Failed benchmark → strongly negative reward
        if not result.success:
            penalty = -self._lambda_penalty if rollback_triggered else 0.0
            return float(-1.0 + penalty)

        score = float(result.score)
        # Invert so "higher is always better" internally
        if not result.score_is_higher_better:
            score = -score

        self._sample_count += 1

        # Update EMA baseline (§2.5 — warmup to avoid initialisation bias)
        if self._ema_baseline is None:
            self._ema_baseline = score
        else:
            self._ema_baseline = (
                self._ema_alpha * score
                + (1.0 - self._ema_alpha) * self._ema_baseline
            )

        # During warmup, return only the stability/penalty component
        # so the agent doesn't get a free positive reward on the
        # very first step before the baseline has stabilised (§2.5).
        if self._sample_count <= self._warmup_steps:
            reward = 0.0
        else:
            baseline = self._ema_baseline
            # Normalise: how much better (or worse) than recent average?
            denom = abs(baseline) + 1e-9
            normalised = (score - baseline) / denom
            normalised = max(-1.0, min(1.0, normalised))
            reward = normalised

        if rollback_triggered:
            reward -= self._lambda_penalty
        else:
            reward += self._lambda_stability

        return float(reward)

    def reset(self) -> None:
        """Optional: clear EMA baseline. Usually NOT called between episodes
        so the baseline tracks long-term system performance trends.
        """
        self._ema_baseline = None
        self._sample_count = 0
