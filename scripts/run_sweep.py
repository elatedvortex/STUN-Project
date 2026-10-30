#!/usr/bin/env python3
"""scripts/run_sweep.py — Brute-force scheduler parameter sweep CLI.

Usage examples
--------------
  # Dry-run coordinate sweep for every workload type (safe, no sysctl writes)
  python3 scripts/run_sweep.py --dry-run --steps 5 -v

  # Real sweep for gaming workload only, 7 steps, save to data/sweep.db
  sudo python3 scripts/run_sweep.py --workload gaming --steps 7 --db data/sweep.db -v
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.adapters import (
    StressNgAdapter, SysbenchAdapter, HackbenchAdapter,
    CyclictestAdapter, FioAdapter, GamingAdapter,
)
from benchmarks.sweep import ParameterSweep
from config.loader import build_registry_from_config
from monitor.collector import Monitor
from monitor.types import SystemSnapshot
from scheduler.controller import SchedulerController
from scheduler.exceptions import RecoveryError
from safety.session import TrainingSession
from safety.checkpoint import CheckpointManager
from scheduler.validator import Validator
from scheduler.writer import Writer
from scheduler.rollback import RollbackStack
from scheduler.profile import ProfileStore
from safety.validator import SecondaryValidator
from storage.db import StorageBackend
from workload.categories import CATEGORY_TO_BENCHMARK_TYPE

log = logging.getLogger('run_sweep')

_ADAPTER_MAP = {
    'cpu':         StressNgAdapter,
    'memory':      SysbenchAdapter,
    'mixed':       HackbenchAdapter,
    'interactive': CyclictestAdapter,
    'io':          FioAdapter,
    'gaming':      GamingAdapter,
}

_ALL_WORKLOAD_TYPES = list(dict.fromkeys(CATEGORY_TO_BENCHMARK_TYPE.values()))


class _DryRunBackend:
    def __init__(self, registry):
        self.state = {}
        for p in registry.get_all():
            lo = float(p.min_value) if p.min_value is not None else 0.0
            hi = float(p.max_value) if p.max_value is not None else (lo * 2.0 or 1.0)
            self.state[p.path] = str(p.type((lo + hi) / 2.0))

    def write(self, path, value):
        self.state[path] = str(value)

    def read(self, path):
        return self.state.get(path, '0')


class _DryRunBenchmark:
    def __init__(self, workload_type, backend):
        self.name = f'dry-{workload_type}'
        self.workload_type = workload_type
        self._backend = backend

    def run(self, **kwargs):
        import random
        from benchmarks.types import BenchmarkResult
        total = sum(float(v) for v in self._backend.state.values() if _is_float(v))
        n = len(self._backend.state)
        score = 100.0 + (total / max(n, 1)) / 1e6 * 10.0 + random.gauss(0, 2)
        return BenchmarkResult(
            name=self.name, workload_type=self.workload_type,
            success=True, score=score, score_is_higher_better=True,
            metrics={'score': score},
        )


def _is_float(v):
    try:
        float(v)
        return True
    except Exception:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description='Brute-force scheduler parameter sweep')
    parser.add_argument('--config',   default='config/scheduler.yaml',
                        help='Scheduler YAML config (default: config/scheduler.yaml)')
    parser.add_argument('--db',       default='data/sweep.db',
                        help='SQLite output path (default: data/sweep.db)')
    parser.add_argument('--workload', default=None,
                        help=f'Workload type to sweep. One of: {_ALL_WORKLOAD_TYPES}. Omit for all.')
    parser.add_argument('--steps',    type=int, default=5,
                        help='Grid steps per parameter (default 5)')
    parser.add_argument('--strategy', choices=['coordinate', 'cartesian'],
                        default='coordinate',
                        help='Sweep strategy (default: coordinate)')
    parser.add_argument('--dry-run',  action='store_true',
                        help='Skip real sysctl writes (safe for testing)')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s %(levelname)-8s %(name)s: %(message)s',
    )

    config_path = Path(args.config)
    if not config_path.exists():
        log.error('Config not found: %s', config_path)
        sys.exit(1)
    registry = build_registry_from_config(str(config_path))
    log.info('Loaded %d parameters from %s', len(registry.get_all()), config_path)

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    storage = StorageBackend(db_path)
    log.info('Results will be stored in %s', db_path)

    if args.dry_run:
        dry_backend = _DryRunBackend(registry)
        writer = Writer(registry, backend=dry_backend)
        def benchmark_factory(wt: str):
            return _DryRunBenchmark(wt, dry_backend)
    else:
        writer = Writer(registry)
        def benchmark_factory(wt: str):
            cls = _ADAPTER_MAP.get(wt, StressNgAdapter)
            return cls()

    validator = Validator(registry)
    rb = RollbackStack()
    profile = ProfileStore()
    secondary = SecondaryValidator()

    controller = SchedulerController(
        registry, validator, writer, rb, profile,
        secondary_validator=secondary,
        storage_backend=storage,
    )

    if args.workload:
        if args.workload not in _ALL_WORKLOAD_TYPES:
            log.error('Unknown workload type %r. Choose from: %s', args.workload, _ALL_WORKLOAD_TYPES)
            sys.exit(1)
        workload_types = [args.workload]
    else:
        workload_types = _ALL_WORKLOAD_TYPES

    sweep_obj = ParameterSweep(
        registry=registry, controller=controller, storage=storage,
        benchmark_factory=benchmark_factory, steps_per_param=args.steps,
        strategy=args.strategy, dry_run=args.dry_run,
    )
    est = sweep_obj.estimate_run_count()
    log.info(
        'Estimated runs per workload: coordinate=%d  cartesian=%d (using %s)',
        est['coordinate'], est['cartesian'], args.strategy,
    )

    checkpoint_path = str(db_path.with_suffix(".dry-run-safety.json")) if args.dry_run else "data/safety_checkpoint.json"
    with TrainingSession(controller, CheckpointManager(checkpoint_path), timeout_sec=360.0) as session:
        sweep_obj.watchdog = session.watchdog
        summaries = []
        for wt in workload_types:
            log.info('SWEEP: workload_type=%r', wt)
            try:
                summary = sweep_obj.run(wt)
                summaries.append(summary)
            except RecoveryError:
                raise
            except Exception:
                log.exception('Sweep failed for workload_type=%r', wt)
                continue

            log.info(
                '  Done: %d/%d successful  best_score=%.4f',
                summary.successful_runs, summary.total_runs, summary.best_score,
            )

    print()
    print('=' * 70)
    print('BEST PARAMS PER WORKLOAD TYPE')
    print('=' * 70)
    for summary in summaries:
        direction = '↑' if summary.score_is_higher_better else '↓'
        print(f'[{summary.workload_type}]  score={summary.best_score:.4f} {direction}')
        print(f'  runs: {summary.successful_runs}/{summary.total_runs} OK')
        for name, val in summary.best_params.items():
            print(f'    {name:40s} = {val}')
        print()
    print('=' * 70)
    print(f'Results stored in: {args.db}')
    print('Run live tuner:  python3 scripts/run_live_tuner.py --sweep-db ' + str(args.db))


if __name__ == '__main__':
    main()
