#!/usr/bin/env python3
"""
M3 demo: run one episode of LinuxSchedulerEnv with a RandomAgent.

Usage
-----
  # Dry-run (fake monitor + fake benchmark, no sysctl writes)
  python3 scripts/run_rl.py --steps 10 --dry-run

  # Live run (real monitor, real benchmark tool required)
  python3 scripts/run_rl.py --steps 20 --benchmark stress-ng
"""

import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import datetime, timezone
from monitor.types import SystemSnapshot
from monitor.collector import Monitor, default_sources
from benchmarks.types import BenchmarkResult
from benchmarks.base import BenchmarkRunner
from benchmarks.adapters import StressNgAdapter
from scheduler import (
    ParameterMeta,
    ParameterRegistry,
    Validator,
    Writer,
    RollbackStack,
    ProfileStore,
    SchedulerController,
    SchedulerBackend,
)
from rl.env import LinuxSchedulerEnv
from core.loop import EpisodeRunner, RandomAgent


# ---------------------------------------------------------------------------
# Fake components for dry-run
# ---------------------------------------------------------------------------

class DryRunBackend(SchedulerBackend):
    """In-memory backend — never touches real sysctl."""
    def __init__(self):
        self.state = {
            "kernel.sched_min_granularity_ns": "3000000",
            "kernel.sched_wakeup_granularity_ns": "4000000",
        }

    def write(self, path, value):
        self.state[path] = str(value)

    def read(self, path):
        return self.state.get(path, "0")


class DryRunMonitor:
    def read_snapshot(self):
        return SystemSnapshot(
            timestamp=datetime.now(timezone.utc),
            cpu_util_pct=45.0,
            load_avg_1=1.2,
            load_avg_5=1.0,
            mem_util_pct=35.0,
            ctxt_switches_delta=50_000,
            runnable_procs=3,
        )


class DryRunBenchmark(BenchmarkRunner):
    def __init__(self):
        super().__init__(name="dry-run", workload_type="cpu")

    def run(self, **kwargs) -> BenchmarkResult:
        import random
        score = 100.0 + random.gauss(0, 5)
        return BenchmarkResult(
            name=self.name, workload_type=self.workload_type,
            success=True, score=score, score_is_higher_better=True,
            metrics={"ops": score},
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="M3 RL environment demo")
    parser.add_argument("--steps", type=int, default=10, help="Episode length")
    parser.add_argument("--dry-run", action="store_true", help="Use fake components (default)")
    parser.add_argument("--benchmark", choices=["stress-ng"], default=None,
                        help="Real benchmark tool to use (requires tool installed)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    log = logging.getLogger("run_rl")

    # --- Registry ---
    registry = ParameterRegistry()
    registry.register(ParameterMeta(
        "sched_min_granularity_ns", int, 100_000, 100_000_000,
        backend="sysctl", path="kernel.sched_min_granularity_ns",
    ))
    registry.register(ParameterMeta(
        "sched_wakeup_granularity_ns", int, 100_000, 100_000_000,
        backend="sysctl", path="kernel.sched_wakeup_granularity_ns",
    ))

    # --- Backend + Controller ---
    use_dry_run = args.dry_run or args.benchmark is None
    if use_dry_run:
        log.info("Dry-run mode: using fake backend, monitor, and benchmark")
        backend = DryRunBackend()
        monitor = DryRunMonitor()
        benchmark = DryRunBenchmark()
    else:
        log.info("Live mode: using real monitor and %s benchmark", args.benchmark)
        backend = DryRunBackend()  # still fake backend — safe for demo
        monitor = Monitor(sources=default_sources())
        monitor.check_capabilities()
        benchmark = StressNgAdapter()

    validator = Validator(registry)
    writer = Writer(registry, backend=backend)
    rollback_stack = RollbackStack()
    profile_store = ProfileStore()
    controller = SchedulerController(registry, validator, writer, rollback_stack, profile_store)

    # --- Environment ---
    env = LinuxSchedulerEnv(
        controller=controller,
        monitor=monitor,
        benchmark=benchmark,
        registry=registry,
        episode_steps=args.steps,
    )

    # --- Agent (random for demo) ---
    agent = RandomAgent(env.action_space)

    # --- Run episode ---
    runner = EpisodeRunner(env=env, agent=agent)
    log.info("Running episode with %d steps...", args.steps)
    stats = runner.run_episode()

    print("\n--- Episode Summary ---")
    for k, v in stats.items():
        print(f"  {k:<18} {v:.4f}" if isinstance(v, float) else f"  {k:<18} {v}")


if __name__ == "__main__":
    main()
