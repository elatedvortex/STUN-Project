#!/usr/bin/env python3
"""
scripts/run_benchmarks.py — Standalone benchmark sweep runner.

Runs the enabled benchmark adapters (optionally driven by a YAML config),
persists every result to a SQLite database, and prints a summary table.

Usage
-----
  # Quick run with built-in defaults (stress-ng + sysbench + hackbench)
  python3 scripts/run_benchmarks.py --db data/benchmarks.db -v

  # YAML-driven (controls which adapters run, how many repeats, kwargs)
  python3 scripts/run_benchmarks.py --config config/benchmarks.yaml -v

  # Single adapter
  python3 scripts/run_benchmarks.py --only stress-ng --repeats 5 -v

  # Label results for comparison
  python3 scripts/run_benchmarks.py --tag pre-tuning  -v
  python3 scripts/run_benchmarks.py --tag post-tuning -v
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.adapters import (
    StressNgAdapter, SysbenchAdapter, HackbenchAdapter,
    CyclictestAdapter, FioAdapter,
)
from benchmarks.base import BenchmarkRunner
from benchmarks.types import BenchmarkResult
from config.loader import (
    load_config, save_default_configs,
    BenchmarkAdapterConfig, BenchmarkConfig,
)
from storage.db import StorageBackend

log = logging.getLogger("run_benchmarks")

# Map config name → adapter class
_ADAPTERS = {
    "stress-ng":  StressNgAdapter,
    "sysbench":   SysbenchAdapter,
    "hackbench":  HackbenchAdapter,
    "cyclictest": CyclictestAdapter,
    "fio":        FioAdapter,
}

# ---------------------------------------------------------------------------
# Built-in default sweep (used when no config file is provided)
# ---------------------------------------------------------------------------

_DEFAULT_SWEEP: List[BenchmarkAdapterConfig] = [
    BenchmarkAdapterConfig("stress-ng",  kwargs={"timeout": 5, "workers": 2}),
    BenchmarkAdapterConfig("sysbench",   kwargs={"timeout": 5, "threads": 2}),
    BenchmarkAdapterConfig("hackbench",  kwargs={"groups": 1, "loops": 100}),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_adapter(
    adapter_cfg: BenchmarkAdapterConfig,
    db: StorageBackend,
    tag: Optional[str] = None,
    verbose: bool = False,
) -> BenchmarkResult:
    """Instantiate the adapter, run it, persist result, return result."""
    adapter_cls = _ADAPTERS.get(adapter_cfg.name)
    if adapter_cls is None:
        log.error("Unknown adapter: %s — skipping", adapter_cfg.name)
        return BenchmarkResult(
            name=adapter_cfg.name,
            workload_type="unknown",
            success=False,
            score=0.0,
            score_is_higher_better=True,
            error_message=f"No adapter registered for '{adapter_cfg.name}'",
        )

    adapter: BenchmarkRunner = adapter_cls()
    log.info("  Running %s %s…", adapter_cfg.name, adapter_cfg.kwargs or "")
    result = adapter.run(**adapter_cfg.kwargs)

    effective_tag = adapter_cfg.tag or tag

    db.write_benchmark_result(
        name=result.name,
        workload_type=result.workload_type,
        success=result.success,
        score=result.score,
        score_is_higher_better=result.score_is_higher_better,
        metrics=result.metrics,
        raw_output=result.raw_output,
        error_message=result.error_message,
        tag=effective_tag,
    )

    if verbose:
        status = "✓" if result.success else "✗"
        direction = "↑" if result.score_is_higher_better else "↓"
        log.info(
            "    %s  score=%.4f %s  metrics=%s  tag=%s",
            status, result.score, direction,
            {k: f"{v:.3g}" for k, v in result.metrics.items()},
            effective_tag or "—",
        )
    return result


def _print_summary(results: List[BenchmarkResult]) -> None:
    """Print a human-readable summary table to stdout."""
    col_w = [20, 12, 10, 6, 30]
    header = (
        f"{'Adapter':<{col_w[0]}} {'Score':>{col_w[1]}} "
        f"{'Direction':<{col_w[2]}} {'OK':<{col_w[3]}} {'Error':<{col_w[4]}}"
    )
    sep = "─" * sum(col_w + [4])
    print(f"\n{sep}")
    print(header)
    print(sep)
    for r in results:
        direction = "higher↑" if r.score_is_higher_better else "lower↓"
        ok = "yes" if r.success else "no"
        err = (r.error_message or "")[:col_w[4]]
        print(
            f"{r.name:<{col_w[0]}} {r.score:>{col_w[1]}.4f} "
            f"{direction:<{col_w[2]}} {ok:<{col_w[3]}} {err:<{col_w[4]}}"
        )
    print(sep)
    n_ok = sum(1 for r in results if r.success)
    print(f"  {n_ok}/{len(results)} runs succeeded.\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark sweep runner")
    parser.add_argument("--config",   default=None,         help="Path to YAML config file")
    parser.add_argument("--db",       default=None,         help="Override SQLite DB path")
    parser.add_argument("--repeats",  type=int, default=None, help="Override repeat count")
    parser.add_argument("--only",     default=None,         help="Run only this adapter (name)")
    parser.add_argument("--tag",      default=None,         help="Label all results with this tag")
    parser.add_argument("--init-config", action="store_true",
                        help="Write example YAML configs to config/ and exit")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    if args.init_config:
        save_default_configs()
        log.info("Example configs written to config/")
        return

    # ── Load config ──────────────────────────────────────────────────────
    if args.config:
        cfg = load_config(args.config)
        bench_cfg = cfg.benchmarks
        log.info("Loaded config from %s", args.config)
    else:
        bench_cfg = BenchmarkConfig(adapters=_DEFAULT_SWEEP)
        log.info("Using built-in default adapter sweep")

    # CLI overrides
    if args.db:
        bench_cfg.db_path = args.db
    if args.repeats is not None:
        bench_cfg.repeats = args.repeats

    # Filter to single adapter if requested
    adapters_to_run = [
        a for a in bench_cfg.adapters
        if a.enabled and (args.only is None or a.name == args.only)
    ]
    if not adapters_to_run:
        log.warning("No adapters to run (all disabled or --only matched nothing). Exiting.")
        return

    # ── Open DB ──────────────────────────────────────────────────────────
    db_path = Path(bench_cfg.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = StorageBackend(db_path)
    log.info("Results will be written to %s", db_path)

    # ── Run sweep ────────────────────────────────────────────────────────
    all_results: List[BenchmarkResult] = []
    total_runs = len(adapters_to_run) * bench_cfg.repeats

    log.info(
        "Starting sweep: %d adapter(s) × %d repeat(s) = %d runs",
        len(adapters_to_run), bench_cfg.repeats, total_runs,
    )

    for repeat in range(1, bench_cfg.repeats + 1):
        if bench_cfg.repeats > 1:
            log.info("── Repeat %d/%d ──────────────────────────", repeat, bench_cfg.repeats)
        for adapter_cfg in adapters_to_run:
            result = _run_adapter(adapter_cfg, db, tag=args.tag, verbose=args.verbose)
            all_results.append(result)

    # ── Summary ──────────────────────────────────────────────────────────
    _print_summary(all_results)
    log.info(
        "Total rows in benchmark_result table: %d",
        db.count_benchmark_results(),
    )


if __name__ == "__main__":
    main()
