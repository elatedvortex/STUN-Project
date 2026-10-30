"""
WorkloadContextBuilder — extends RL observations with workload + history (M6).

Produces a fixed-length float32 vector appended to the base StateBuilder
output:

  [0..7]   category weights (browser, compiler, …, system)
  [8]      normalised best historical benchmark score for primary category
  [9]      profile distance — mean |current − best| over tunable params
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import numpy as np

from monitor.types import SystemSnapshot
from scheduler.registry import ParameterRegistry
from workload.categories import WORKLOAD_CATEGORIES
from workload.classifier import ProcessClassifier

if TYPE_CHECKING:
    from storage.db import StorageBackend


class WorkloadContextBuilder:
    """Build workload-conditioned context features for the RL observation."""

    _CATEGORY_DIM = len(WORKLOAD_CATEGORIES)
    _HISTORY_DIM = 2  # best_score_norm, profile_distance
    context_dim: int = _CATEGORY_DIM + _HISTORY_DIM

    def __init__(
        self,
        registry: ParameterRegistry,
        storage: Optional["StorageBackend"] = None,
    ) -> None:
        self._registry = registry
        self._storage = storage
        self._classifier = ProcessClassifier()

    def build(self, snapshot: SystemSnapshot) -> np.ndarray:
        ctx = np.zeros(self.context_dim, dtype=np.float32)
        fp = self._classifier.fingerprint(snapshot)

        for i, cat in enumerate(WORKLOAD_CATEGORIES):
            ctx[i] = float(fp.category_weights.get(cat, 0.0))

        if self._storage is None:
            return ctx

        record = self._storage.best_benchmark_for_category(fp.primary_category)
        if record is None:
            return ctx

        ctx[self._CATEGORY_DIM] = _normalise_score(
            record["score"],
            record["score_is_higher_better"],
        )

        hist_params = record.get("sched_params") or {}
        if hist_params and snapshot.sched_params:
            ctx[self._CATEGORY_DIM + 1] = _profile_distance(
                snapshot.sched_params,
                hist_params,
                self._registry,
            )

        return ctx


def _clip(v: float) -> float:
    return max(0.0, min(1.0, v))


def _normalise_score(score: float, higher_is_better: bool) -> float:
    """Map a raw benchmark score into [0, 1] for the observation vector."""
    if not higher_is_better:
        # Lower latency / error is better — invert with a soft scale.
        return _clip(1.0 / (1.0 + max(score, 0.0)))
    # Throughput-style scores — log-scale to keep large ops/sec in range.
    return _clip(np.log1p(max(score, 0.0)) / 10.0)


def _profile_distance(
    current: dict,
    historical: dict,
    registry: ParameterRegistry,
) -> float:
    """Mean normalised absolute difference between current and best-known params."""
    diffs: list[float] = []
    for meta in registry.get_all():
        cur = float(current.get(meta.path, current.get(meta.name, 0.0)))
        hist = float(historical.get(meta.path, historical.get(meta.name, cur)))
        span = float(meta.max_value - meta.min_value) if meta.max_value else 1.0
        if span <= 0:
            continue
        diffs.append(abs(cur - hist) / span)
    if not diffs:
        return 0.0
    return _clip(float(np.mean(diffs)))
