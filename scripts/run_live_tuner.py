#!/usr/bin/env python3
"""scripts/run_live_tuner.py — Live autonomous scheduler tuning agent.

Reads the sweep database produced by run_sweep.py, monitors which
applications are currently running, and automatically applies the
best-known scheduler parameters for the detected workload category.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.live_tuner import LiveTunerAgent
from config.loader import build_registry_from_config
from monitor.collector import Monitor, default_sources
from scheduler.controller import SchedulerController
from scheduler.validator import Validator
from scheduler.writer import Writer
from scheduler.rollback import RollbackStack
from scheduler.profile import ProfileStore
from safety.validator import SecondaryValidator
from safety.session import TrainingSession
from safety.checkpoint import CheckpointManager
from storage.db import StorageBackend

log = logging.getLogger('run_live_tuner')


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


def main() -> None:
    parser = argparse.ArgumentParser(description='Live autonomous scheduler tuning agent')
    parser.add_argument('--sweep-db',  required=True,
                        help='Path to sweep SQLite DB produced by run_sweep.py')
    parser.add_argument('--config',    default='config/scheduler.yaml',
                        help='Scheduler YAML config (default: config/scheduler.yaml)')
    parser.add_argument('--interval',  type=float, default=10.0,
                        help='Poll interval in seconds (default 10)')
    parser.add_argument('--cache-ttl', type=float, default=300.0,
                        help='Best-params cache TTL in seconds (default 300)')
    parser.add_argument('--dry-run',   action='store_true',
                        help='Skip real sysctl writes (safe for testing)')
    parser.add_argument('--once',      action='store_true',
                        help='Run one cycle and exit (useful for testing)')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s %(levelname)-8s %(name)s: %(message)s',
    )

    config_path = Path(args.config)
    if not config_path.exists():
        log.error('Scheduler config not found: %s', config_path)
        sys.exit(1)

    sweep_db_path = Path(args.sweep_db)
    if not sweep_db_path.exists():
        log.error('Sweep DB not found: %s', sweep_db_path)
        sys.exit(1)

    registry = build_registry_from_config(str(config_path))
    log.info('Loaded %d parameters from %s', len(registry.get_all()), config_path)

    storage = StorageBackend(sweep_db_path)
    available_wt = storage.list_sweep_workload_types()
    if not available_wt:
        log.warning(
            'Sweep DB has no sweep results (tag="sweep:*"). '
            'Run run_sweep.py first to populate it.'
        )
    else:
        log.info('Sweep DB contains results for workload types: %s', available_wt)

    sched_keys = tuple(m.path for m in registry.get_all())
    monitor = Monitor(sources=default_sources(sched_param_keys=sched_keys))

    if args.dry_run:
        dry_backend = _DryRunBackend(registry)
        writer = Writer(registry, backend=dry_backend)
    else:
        writer = Writer(registry)

    validator = Validator(registry)
    rb = RollbackStack()
    profile = ProfileStore()
    secondary = SecondaryValidator()

    controller = SchedulerController(
        registry, validator, writer, rb, profile,
        secondary_validator=secondary,
        storage_backend=storage,
    )

    agent = LiveTunerAgent(
        monitor=monitor,
        controller=controller,
        storage=storage,
        registry=registry,
        poll_interval=args.interval,
        dry_run=args.dry_run,
        cache_ttl=args.cache_ttl,
    )

    log.info(
        'Starting LiveTunerAgent  interval=%.1fs  dry_run=%s  sweep_db=%s',
        args.interval, args.dry_run, sweep_db_path,
    )

    checkpoint_path = str(sweep_db_path.with_suffix(".live-dry-run-safety.json")) if args.dry_run else "data/safety_checkpoint.json"
    with TrainingSession(controller, CheckpointManager(checkpoint_path),
                         timeout_sec=max(120.0, args.interval * 3)) as session:
        agent.watchdog = session.watchdog
        if args.once:
            status = agent.run_once()
            log.info('Single-cycle result: %s', status)
        else:
            agent.run_forever()


if __name__ == '__main__':
    main()
