#!/usr/bin/env python3
"""Demo runner for the SelfTunerAgent using dry-run backends.

Runs one or more tuning iterations without touching real sysctls.
"""
import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone

# Ensure project package imports work when run from scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.loader import build_registry_from_config
from monitor.collector import Monitor
from storage.db import StorageBackend
from benchmarks.base import BenchmarkRunner
from scheduler.writer import Writer
from scheduler.validator import Validator
from scheduler.rollback import RollbackStack
from scheduler.profile import ProfileStore
from scheduler.controller import SchedulerController
from safety.validator import SecondaryValidator

from agents.self_tuner import SelfTunerAgent


class _DryRunBackend:
    def __init__(self, registry):
        self.state = {}
        for p in registry.get_all():
            lo = float(p.min_value) if p.min_value is not None else 0.0
            hi = float(p.max_value) if p.max_value is not None else 1.0
            self.state[p.path] = str(p.type((lo + hi) / 2.0))

    def write(self, path, value):
        self.state[path] = str(value)

    def read(self, path):
        return self.state.get(path, "0")


class _DryRunMonitor(Monitor):
    def __init__(self, backend):
        self._backend = backend

    def read_snapshot(self):
        # lightweight synthetic snapshot — reuse monitor types without
        # running real /proc reads for the demo
        import random
        from monitor.types import SystemSnapshot

        # expose the dry-run backend's current state as sched_params so the
        # tuner can read current values and propose perturbations
        sched = {}
        for path, raw in self._backend.state.items():
            try:
                sched[path] = float(raw)
            except Exception:
                continue

        return SystemSnapshot(
            timestamp=datetime.now(timezone.utc),
            cpu_util_pct=45.0 + random.gauss(0, 5),
            load_avg_1=1.2, load_avg_5=1.0,
            mem_util_pct=35.0, ctxt_switches_delta=50_000, runnable_procs=3,
            sched_params=sched,
        )


class _DryRunBenchmark(BenchmarkRunner):
    def __init__(self, backend: _DryRunBackend):
        super().__init__(name="dry-run", workload_type="cpu")
        self._backend = backend

    def run(self, **kwargs):
        # create a score that depends on backend state so tuning has signal
        import random
        total = 0.0
        n = 0
        for raw in self._backend.state.values():
            try:
                total += float(raw)
                n += 1
            except Exception:
                pass
        base = (total / max(n, 1)) / 1e6
        score = 100.0 + base * 10.0 + random.gauss(0, 2)
        from benchmarks.types import BenchmarkResult

        return BenchmarkResult(self.name, self.workload_type, True, score, True, {"ops": score})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    registry = build_registry_from_config("config/scheduler.yaml")
    storage = StorageBackend(":memory:")

    # dry-run wiring (safe)
    backend = _DryRunBackend(registry)
    monitor = _DryRunMonitor(backend)
    benchmark_factory = lambda _type: _DryRunBenchmark(backend)

    writer = Writer(registry, backend=backend)
    validator = Validator(registry)
    rb = RollbackStack()
    profile = ProfileStore()
    secondary = SecondaryValidator()

    controller = SchedulerController(
        registry, validator, writer, rb, profile,
        secondary_validator=secondary, storage_backend=storage,
    )

    agent = SelfTunerAgent(
        monitor=monitor,
        controller=controller,
        storage=storage,
        registry=registry,
        benchmark_factory=benchmark_factory,
    )

    for i in range(args.iterations):
        logging.info("Iteration %d/%d", i + 1, args.iterations)
        out = agent.run_tuning_iteration(run_benchmark=True)
        logging.info("Result: proposal=%s benchmark=%s", out["proposal"], getattr(out["benchmark"], "score", None))


if __name__ == "__main__":
    main()
