"""Self-tuning agent that observes the system, proposes scheduler parameter
changes, and evaluates those changes with benchmarks.

This module implements a conservative, pluggable agent that:
- observes `Monitor.read_snapshot()` and classifies running processes
- attempts to reuse the best historical benchmark parameters when available
- otherwise perturbs current scheduler parameters (safe, small changes)
- applies proposals via `SchedulerController.apply_parameters()`
- runs a benchmark and persists the result to `StorageBackend`

The agent is intentionally small and dependency-injected so callers may
wire real or dry-run backends for safe testing.
"""
from __future__ import annotations

import logging
import random
from typing import Any, Callable, Dict, Optional

from monitor.collector import Monitor
from workload.classifier import ProcessClassifier
from storage.db import StorageBackend
from scheduler.registry import ParameterRegistry
from scheduler.controller import SchedulerController
from scheduler.exceptions import RecoveryError
from benchmarks.base import BenchmarkRunner

logger = logging.getLogger(__name__)


class SelfTunerAgent:
    def __init__(
        self,
        monitor: Monitor,
        controller: SchedulerController,
        storage: StorageBackend,
        registry: ParameterRegistry,
        benchmark_factory: Optional[Callable[[str], BenchmarkRunner]] = None,
        classifier: Optional[ProcessClassifier] = None,
    ) -> None:
        self.monitor = monitor
        self.controller = controller
        self.storage = storage
        self.registry = registry
        self.benchmark_factory = benchmark_factory
        self.classifier = classifier or ProcessClassifier()

    def _convert_sched_params_to_registry_names(self, sched_params: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a mapping of sysctl paths -> values (as stored in DB/snapshots)
        to registry logical names -> casted values suitable for `apply_parameters()`.
        """
        out: Dict[str, Any] = {}
        for meta in self.registry.get_all():
            if meta.path in sched_params:
                try:
                    out[meta.name] = meta.type(sched_params[meta.path])
                except Exception:
                    # Skip values that can't be cast
                    continue
        return out

    def observe_and_classify(self):
        snap = self.monitor.read_snapshot()
        fingerprint = self.classifier.fingerprint(snap)
        return snap, fingerprint

    def suggest_from_history(self, category: str) -> Optional[Dict[str, Any]]:
        best = self.storage.best_benchmark_for_category(category)
        if not best or not best.get("sched_params"):
            return None
        return self._convert_sched_params_to_registry_names(best["sched_params"])

    def heuristic_perturb(self, snapshot, fingerprint) -> Dict[str, Any]:
        """Create a small perturbation of current scheduler params.

        Strategy: take current value from snapshot.sched_params (which uses
        sysctl paths) and apply a small multiplicative delta. This is a
        conservative exploration strategy suitable for initial testing.
        """
        params: Dict[str, Any] = {}
        # bias direction depending on primary category (cpu-heavy -> increase)
        cpu_like = {"compiler", "system", "container", "database"}
        primary = fingerprint.primary_category
        direction = 0.08 if primary in cpu_like else -0.05

        for meta in self.registry.get_all():
            cur = None
            # snapshot.sched_params keys are sysctl paths
            try:
                cur = snapshot.sched_params.get(meta.path)
            except Exception:
                cur = None
            if cur is None:
                # If snapshot doesn't expose the key, skip it
                continue
            try:
                cur_val = float(cur)
            except Exception:
                continue

            # small random factor to encourage exploration
            rand = random.uniform(-0.03, 0.03)
            delta = direction + rand
            new = cur_val * (1.0 + delta)
            # clamp to meta bounds when present
            if meta.min_value is not None:
                new = max(new, float(meta.min_value))
            if meta.max_value is not None:
                new = min(new, float(meta.max_value))
            try:
                params[meta.name] = meta.type(new)
            except Exception:
                # fallback: skip parameter if casting fails
                continue

        return params

    def run_tuning_iteration(self, run_benchmark: bool = True, bench_kwargs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """One observe -> propose -> apply -> (benchmark) iteration.

        Returns a dict containing snapshot, fingerprint, proposal, and
        benchmark_result (if run).
        """
        snapshot, fingerprint = self.observe_and_classify()
        proposal = self.suggest_from_history(fingerprint.primary_category)

        if proposal is None:
            proposal = self.heuristic_perturb(snapshot, fingerprint)

        result: Dict[str, Any] = {
            "snapshot": snapshot,
            "fingerprint": fingerprint,
            "proposal": proposal,
            "benchmark": None,
        }

        if not proposal:
            logger.info("No candidate parameters proposed; skipping apply")
            return result

        # Try applying proposal through the controller safety pipeline
        try:
            self.controller.apply_parameters(proposal)
            logger.info("Applied proposal: %s", proposal)
        except RecoveryError:
            raise
        except Exception as exc:
            logger.warning("Failed to apply proposal: %s", exc)
            # Failed transactions are restored by the controller. Do not undo
            # an earlier successful proposal with an additional rollback.
            return result

        # Optionally run a benchmark to evaluate the new state
        if run_benchmark and self.benchmark_factory is not None:
            bench_type = fingerprint.benchmark_workload_type
            try:
                bench_runner = self.benchmark_factory(bench_type)
                bench_res = bench_runner.run(**(bench_kwargs or {}))
            except Exception as exc:
                logger.exception("Benchmark run failed: %s", exc)
                bench_res = None

            if bench_res is not None:
                # Persist benchmark and include useful metadata
                metrics = dict(bench_res.metrics or {})
                metrics.setdefault("primary_category", fingerprint.primary_category)
                # store sched params as sysctl-path keyed map for auditability
                sched_map = {}
                for meta_name, val in proposal.items():
                    try:
                        meta = next(m for m in self.registry.get_all() if m.name == meta_name)
                        sched_map[meta.path] = val
                    except StopIteration:
                        continue
                metrics.setdefault("sched_params", sched_map)

                try:
                    self.storage.write_benchmark_result(
                        name=bench_res.name,
                        workload_type=bench_res.workload_type,
                        success=bench_res.success,
                        score=bench_res.score,
                        score_is_higher_better=bench_res.score_is_higher_better,
                        metrics=metrics,
                        raw_output=bench_res.raw_output,
                        error_message=bench_res.error_message,
                        tag="self_tuner",
                    )
                except Exception:
                    logger.exception("Failed to persist benchmark result")

            result["benchmark"] = bench_res

        return result
