"""
Process-based workload fingerprinting (M6).

Builds a WorkloadFingerprint from the process sample embedded in a
SystemSnapshot. Uses interval CPU ticks when available. Lifetime totals are a
labelled fallback for legacy snapshots, not a measure of current CPU activity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from monitor.types import ProcessInfo, SystemSnapshot
from workload.categories import WORKLOAD_CATEGORIES, classify_comm


@dataclass(frozen=True)
class WorkloadFingerprint:
    """Summary of the active workload derived from running processes."""

    category_weights: Mapping[str, float]
    primary_category: str
    top_processes: tuple[tuple[str, float], ...]
    measurement_basis: str = "lifetime"
    observed_cpu_ticks: float = 0.0
    classified_cpu_fraction: float = 0.0

    @property
    def benchmark_workload_type(self) -> str:
        from workload.categories import CATEGORY_TO_BENCHMARK_TYPE
        return CATEGORY_TO_BENCHMARK_TYPE.get(self.primary_category, "mixed")


class ProcessClassifier:
    """Classify processes in a snapshot into workload categories."""

    def fingerprint(self, snapshot: SystemSnapshot) -> WorkloadFingerprint:
        weights: dict[str, float] = {cat: 0.0 for cat in WORKLOAD_CATEGORIES}
        proc_weights: list[tuple[str, float]] = []
        interval = any(proc.cpu_ticks_delta is not None for proc in snapshot.processes)
        observed = 0.0

        for proc in snapshot.processes:
            tick_weight = (float(proc.cpu_ticks_delta or 0) if interval
                           else max(1.0, float(proc.utime + proc.stime)))
            tick_weight = max(0.0, tick_weight)
            observed += tick_weight
            category = classify_comm(proc.comm)
            if category is None or tick_weight == 0:
                continue
            weights[category] += tick_weight
            proc_weights.append((proc.comm, tick_weight))

        total = sum(weights.values())
        if total > 0:
            for cat in WORKLOAD_CATEGORIES:
                weights[cat] /= total
            primary = max(WORKLOAD_CATEGORIES, key=lambda c: weights[c])
        else:
            # No classifiable processes — uniform prior so obs stays in-range.
            uniform = 1.0 / len(WORKLOAD_CATEGORIES)
            weights = {cat: uniform for cat in WORKLOAD_CATEGORIES}
            primary = "system"

        proc_weights.sort(key=lambda x: x[1], reverse=True)
        top = tuple(proc_weights[:5])

        return WorkloadFingerprint(
            category_weights=weights,
            primary_category=primary,
            top_processes=top,
            measurement_basis="interval" if interval else "lifetime",
            observed_cpu_ticks=observed,
            classified_cpu_fraction=total / observed if observed else 0.0,
        )
