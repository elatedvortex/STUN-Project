# M1 — Monitor + Storage skeleton

Status: **built and passing** in this environment.

## What's here

- `monitor/types.py` — `SystemSnapshot`, the single data contract every
  downstream module (classifier, RL state builder, dashboard) will consume.
- `monitor/sources.py` — one `MetricSource` per Linux interface:
  `ProcStatSource`, `ProcLoadAvgSource`, `ProcMemInfoSource`, `CpuFreqSource`,
  `SysctlSchedSource`, `NumaSource`, `ProcessSampleSource`, and an optional
  `PerfStatSource` (excluded from the default set — expensive, permission-sensitive).
- `monitor/collector.py` — `Monitor`, which runs capability detection once
  at startup and assembles active sources into a `SystemSnapshot` on demand.
- `storage/db.py` — SQLite-backed `StorageBackend` for the `snapshot` table
  (the full multi-table schema in the architecture doc lands with the RL
  training loop in later milestones).
- `scripts/run_monitor.py` — CLI demo: collects for N seconds, persists
  every snapshot, prints a summary.
- `tests/test_monitor.py` — 12 unit tests, all against fakes/tmp_path
  fixtures, no root and no dependency on the host kernel's actual `/proc`
  layout.

## Run it

```bash
pip install -r requirements.txt
python3 scripts/run_monitor.py --duration 15 --interval 1.0 --db data/monitor.db -v
```

## Test it

```bash
python3 -m pytest tests/ -v
```

## What was verified in this sandbox

This container has no `sched_*` sysctls and no `cpufreq` exposed, but real
`/proc/stat`, `/proc/loadavg`, `/proc/meminfo`, and partial NUMA info. Running
the demo here confirmed:

- Capability detection correctly reports `cpu_freq=no, sysctl_sched=no` and
  everything else `yes`, and the collector skips the unavailable sources
  without error.
- `ProcStatSource.cpu_util_pct` is `None` on the very first snapshot (no
  baseline yet to diff against) and populated from the second snapshot on —
  this is expected behavior, not a bug, and is worth a sentence in your
  methodology write-up.
- A unit test caught a real bug during development: a malformed `cpu` line
  in `/proc/stat` raised `ValueError` instead of degrading gracefully. Fixed
  to skip just that line (per-line resilience) while still parsing valid
  lines elsewhere in the same read — this is the kind of defensive handling
  the architecture doc's Section 6 testing strategy exists to catch, and
  it caught something real on the first run.

## Known gaps / next milestone's job

- `SysctlSchedSource` is unavailable on kernels without the classic CFS
  sysctl surface (like this container, and like any EEVDF-only 6.6+ kernel —
  see the architecture doc's note on this in Section 1). M2's Scheduler
  Controller will need the same capability-detection discipline.
- `ProcessSampleSource` samples the first N PIDs returned by `os.listdir`,
  which is not a random sample — fine for M1's purpose (proving the
  pipeline), but note this if you use it for anything statistical later.
- No `config/monitor.yaml` loader yet — `run_monitor.py` takes CLI flags
  directly. Config-file-driven experiments (Section 3.9 of the architecture
  doc) start mattering once we're running actual RL training runs, not just
  the monitor in isolation.

## Next

M2: Scheduler Controller (`ParameterRegistry`, `Validator`, `Writer`,
`RollbackStack`) + Safety baseline, per the roadmap in the architecture doc,
Section 5.
