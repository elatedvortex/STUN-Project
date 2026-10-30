"""benchmarks/sweep.py — Brute-force parameter sweep engine.

For each workload type the sweep varies each registered scheduler parameter
one at a time (coordinate descent), benchmarks the result, and records the
best-scoring param set to SQLite.

Results are tagged sweep:<workload_type> so LiveTunerAgent and
StorageBackend.best_params_for_workload() can find them.
"""
from __future__ import annotations

import itertools
import logging
import random
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from benchmarks.base import BenchmarkRunner
from benchmarks.types import BenchmarkResult
from scheduler.controller import SchedulerController
from scheduler.exceptions import RecoveryError
from scheduler.registry import ParameterRegistry
from storage.db import StorageBackend

logger = logging.getLogger(__name__)


@dataclass
class SweepRun:
    """Record of one sweep trial."""
    params: Dict[str, Any]
    result: BenchmarkResult
    iteration: int


@dataclass
class SweepSummary:
    """Returned by ParameterSweep.run()."""
    workload_type: str
    total_runs: int
    successful_runs: int
    best_params: Dict[str, Any]   # logical param name -> value
    best_score: float
    score_is_higher_better: bool
    runs: List[SweepRun] = field(default_factory=list)

    def best_params_as_sysctl(self, registry: ParameterRegistry) -> Dict[str, Any]:
        """Return best_params keyed by sysctl path instead of logical name."""
        out: Dict[str, Any] = {}
        for name, val in self.best_params.items():
            try:
                meta = registry.get(name)
                out[meta.path] = val
            except Exception:
                continue
        return out


def _linspace(lo: float, hi: float, steps: int) -> List[float]:
    if steps <= 1:
        return [(lo + hi) / 2.0]
    step = (hi - lo) / (steps - 1)
    return [lo + i * step for i in range(steps)]


def _candidate_values(meta, steps: int) -> List[Any]:
    lo = float(meta.min_value) if meta.min_value is not None else 0.0
    hi = float(meta.max_value) if meta.max_value is not None else (lo * 2.0 or 1.0)
    raw = _linspace(lo, hi, steps)
    try:
        return [meta.type(v) for v in raw]
    except Exception:
        return raw


class ParameterSweep:
    """Brute-force scheduler parameter sweep.

    Args:
        registry:          ParameterRegistry with tunable params.
        controller:        SchedulerController for apply/rollback.
        storage:           StorageBackend for result persistence.
        benchmark_factory: Callable(workload_type) -> BenchmarkRunner.
        steps_per_param:   Grid density per parameter (default 5).
        strategy:          "coordinate" (fast) or "cartesian" (exhaustive).
        bench_kwargs:      Extra kwargs for BenchmarkRunner.run().
        dry_run:           Skip real sysctl writes if True.
    """

    def __init__(
        self,
        registry: ParameterRegistry,
        controller: SchedulerController,
        storage: StorageBackend,
        benchmark_factory: Callable[[str], BenchmarkRunner],
        steps_per_param: int = 5,
        strategy: str = "coordinate",
        bench_kwargs: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
        watchdog=None,
    ) -> None:
        self.registry = registry
        self.controller = controller
        self.storage = storage
        self.benchmark_factory = benchmark_factory
        self.steps_per_param = steps_per_param
        self.strategy = strategy
        self.bench_kwargs = bench_kwargs or {}
        self.dry_run = dry_run
        self.watchdog = watchdog

    def run(self, workload_type: str) -> SweepSummary:
        """Execute the full sweep for *workload_type*."""
        lease = self.controller.exclusive() if hasattr(self.controller, "exclusive") else nullcontext()
        with lease:
            baseline = (self.controller.read_state() if not self.dry_run
                        and hasattr(self.controller, "read_state") else None)
            try:
                return self._run(workload_type)
            finally:
                if baseline is not None:
                    self.controller.restore_state(baseline)

    def _run(self, workload_type: str) -> SweepSummary:
        params_meta = self.registry.get_all()
        if not params_meta:
            raise ValueError("ParameterRegistry is empty — load scheduler.yaml first")
        tag = f"{'dry-run-sweep' if self.dry_run else 'sweep'}:{workload_type}"
        logger.info(
            "Starting %s sweep  workload=%r  params=%d  steps=%d",
            self.strategy, workload_type, len(params_meta), self.steps_per_param,
        )
        if self.strategy == "cartesian":
            return self._run_cartesian(workload_type, params_meta, tag)
        return self._run_coordinate(workload_type, params_meta, tag)

    def estimate_run_count(self) -> Dict[str, int]:
        """Estimated trial counts — no side effects."""
        n = len(self.registry.get_all())
        s = self.steps_per_param
        return {"coordinate": n * s, "cartesian": s ** n}

    def _run_coordinate(self, workload_type, params_meta, tag) -> SweepSummary:
        best_params: Dict[str, Any] = {}
        for meta in params_meta:
            lo = float(meta.min_value) if meta.min_value is not None else 0.0
            hi = float(meta.max_value) if meta.max_value is not None else (lo * 2.0 or 1.0)
            try:
                best_params[meta.name] = meta.type((lo + hi) / 2.0)
            except Exception:
                best_params[meta.name] = (lo + hi) / 2.0

        best_score: Optional[float] = None
        higher_is_better = True
        runs: List[SweepRun] = []
        iteration = 0

        for meta in params_meta:
            candidates = _candidate_values(meta, self.steps_per_param)
            logger.info("  Sweeping %r over %d values", meta.name, len(candidates))
            for val in candidates:
                trial = dict(best_params)
                trial[meta.name] = val
                result = self._trial(trial, workload_type, tag)
                iteration += 1
                runs.append(SweepRun(params=dict(trial), result=result, iteration=iteration))
                if result.success:
                    score = result.score
                    hib = result.score_is_higher_better
                    higher_is_better = hib
                    is_better = (
                        best_score is None
                        or (hib and score > best_score)
                        or (not hib and score < best_score)
                    )
                    if is_better:
                        best_score = score
                        best_params[meta.name] = val
                        logger.info("    iter=%d  %r=%s  score=%.4f  NEW BEST",
                                    iteration, meta.name, val, score)
                    else:
                        logger.debug("    iter=%d  %r=%s  score=%.4f",
                                     iteration, meta.name, val, score)

        return SweepSummary(
            workload_type=workload_type,
            total_runs=len(runs),
            successful_runs=sum(1 for r in runs if r.result.success),
            best_params=best_params,
            best_score=best_score or 0.0,
            score_is_higher_better=higher_is_better,
            runs=runs,
        )

    def _run_cartesian(self, workload_type, params_meta, tag) -> SweepSummary:
        """Random-sample cartesian search capped at max_trials to avoid OOM.

        Instead of trying all n^s combinations (which explodes exponentially),
        we randomly sample `max_trials` independent configurations. This still
        bounds memory use and benchmark cost; it is not exhaustive search.
        """
        MAX_TRIALS = self.steps_per_param * len(params_meta) * 3  # e.g. 20*8*3 = 480

        names = [m.name for m in params_meta]
        value_lists = [_candidate_values(m, self.steps_per_param) for m in params_meta]

        # Build a pool: full cartesian only if small enough, else random sample
        total_combos = 1
        for vl in value_lists:
            total_combos *= len(vl)

        if total_combos <= MAX_TRIALS:
            combos = list(itertools.product(*value_lists))
            random.shuffle(combos)
        else:
            # Random sampling — pick MAX_TRIALS independent combos
            combos = [
                tuple(random.choice(vl) for vl in value_lists)
                for _ in range(MAX_TRIALS)
            ]

        logger.info(
            "Cartesian sweep (random-sample): %d / %d possible combos",
            len(combos), total_combos,
        )

        best_params: Dict[str, Any] = {}
        best_score: Optional[float] = None
        higher_is_better = True
        runs: List[SweepRun] = []

        for i, combo in enumerate(combos):
            trial = dict(zip(names, combo))
            result = self._trial(trial, workload_type, tag)
            runs.append(SweepRun(params=dict(trial), result=result, iteration=i + 1))
            if result.success:
                score = result.score
                hib = result.score_is_higher_better
                higher_is_better = hib
                is_better = (
                    best_score is None
                    or (hib and score > best_score)
                    or (not hib and score < best_score)
                )
                if is_better:
                    best_score = score
                    best_params = dict(trial)
                    logger.info("iter=%d  NEW BEST  score=%.4f", i + 1, score)

        return SweepSummary(
            workload_type=workload_type,
            total_runs=len(runs),
            successful_runs=sum(1 for r in runs if r.result.success),
            best_params=best_params,
            best_score=best_score or 0.0,
            score_is_higher_better=higher_is_better,
            runs=runs,
        )


    def _trial(self, params: Dict[str, Any], workload_type: str, tag: str) -> BenchmarkResult:
        """Apply params, benchmark, persist, rollback."""
        if self.watchdog is not None:
            if self.watchdog.timed_out:
                raise RecoveryError("Sweep watchdog expired")
            self.watchdog.ping()
        if not self.dry_run:
            try:
                self.controller.apply_parameters(params)
            except RecoveryError:
                raise
            except Exception as exc:
                logger.warning("apply_parameters failed: %s", exc)
                return BenchmarkResult(
                    name="sweep-apply-failed", workload_type=workload_type,
                    success=False, score=0.0, score_is_higher_better=True,
                    error_message=str(exc),
                )

        try:
            bench = self.benchmark_factory(workload_type)
            result = bench.run(**self.bench_kwargs)
        except Exception as exc:
            logger.exception("Benchmark raised: %s", exc)
            result = BenchmarkResult(
                name="sweep-bench-error", workload_type=workload_type,
                success=False, score=0.0, score_is_higher_better=True,
                error_message=str(exc),
            )

        sched_map: Dict[str, Any] = {}
        for name, val in params.items():
            try:
                meta = self.registry.get(name)
                sched_map[meta.path] = val
            except Exception:
                continue

        metrics = dict(result.metrics or {})
        metrics["sched_params"] = sched_map
        metrics["dry_run"] = self.dry_run

        try:
            self.storage.write_benchmark_result(
                name=result.name, workload_type=workload_type,
                success=result.success, score=result.score,
                score_is_higher_better=result.score_is_higher_better,
                metrics=metrics, raw_output=result.raw_output,
                error_message=result.error_message, tag=tag,
            )
        except Exception:
            logger.exception("Failed to persist sweep result")

        if not self.dry_run:
            try:
                self.controller.rollback()
            except Exception as exc:
                raise RecoveryError("Sweep restoration failed; aborting further trials") from exc

        return result
