#!/usr/bin/env python3
"""
M1 demo: run the Monitor for a fixed duration, writing every snapshot to
SQLite, then print a short summary.

Usage:
    python3 scripts/run_monitor.py --duration 30 --interval 1.0 --db data/monitor.db
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from monitor.collector import Monitor  # noqa: E402
from storage.db import StorageBackend  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="M1 monitor demo")
    parser.add_argument("--duration", type=float, default=15.0, help="seconds to run")
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between samples")
    parser.add_argument("--db", type=str, default="data/monitor.db", help="sqlite db path")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    log = logging.getLogger("run_monitor")

    monitor = Monitor()
    capabilities = monitor.check_capabilities()

    available = [name for name, ok in capabilities.items() if ok]
    unavailable = [name for name, ok in capabilities.items() if not ok]
    log.info("available sources : %s", ", ".join(available) or "(none)")
    log.info("unavailable sources: %s", ", ".join(unavailable) or "(none)")

    storage = StorageBackend(args.db)

    start = time.monotonic()
    n = 0
    cpu_samples: list[float] = []
    while time.monotonic() - start < args.duration:
        snapshot = monitor.read_snapshot()
        storage.write_snapshot(snapshot)
        n += 1
        if snapshot.cpu_util_pct is not None:
            cpu_samples.append(snapshot.cpu_util_pct)
        log.debug(
            "snapshot #%d: cpu=%.1f%% load1=%s mem=%.1f%% ctxt_delta=%s procs_sampled=%d",
            n,
            snapshot.cpu_util_pct or 0.0,
            snapshot.load_avg_1,
            snapshot.mem_util_pct or 0.0,
            snapshot.ctxt_switches_delta,
            len(snapshot.processes),
        )
        time.sleep(max(0.0, args.interval))

    total = storage.count_snapshots()
    log.info("collected %d snapshots this run (total in db: %d)", n, total)
    if cpu_samples:
        log.info(
            "cpu_util_pct over this run: min=%.1f avg=%.1f max=%.1f",
            min(cpu_samples),
            sum(cpu_samples) / len(cpu_samples),
            max(cpu_samples),
        )
    log.info("wrote to %s", args.db)


if __name__ == "__main__":
    main()
