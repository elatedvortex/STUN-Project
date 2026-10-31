# Adaptive Reinforcement Learning Framework for Linux Scheduler Optimisation

An experimental framework for monitoring Linux systems and exploring scheduler
parameter tuning through PPO/SAC (Stable-Baselines3), parameter sweeps, and
workload-based configuration selection. Real performance benefits and production
safety require further validation; this repository does not establish them.

The headless **live tuner selects configurations from sweep results**. It does
not run PPO/SAC inference. RL training is a separate path in `scripts/run_training.py`.
See [evaluation and recovery](docs/EVALUATION.md) for measurement procedures,
limitations, and the status of historical presentation figures.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        Dashboard (PyQt6)                         │
│  Overview │ Processes │ Memory │ Scheduler                       │
└──────────────┬───────────────────────────────────────────────────┘
               │ SystemSnapshot (every 1 s)
┌──────────────▼───────────────┐   ┌──────────────────────────────┐
│   Monitor (M1)               │   │   Storage (SQLite)            │
│   ProcStat / MemInfo /       │──▶│   snapshot / benchmark_result │
│   LoadAvg / CpuFreq /        │   │   applied_config              │
│   SysctlSched / NUMA         │   └──────────────────────────────┘
└──────────────────────────────┘
               │ SystemSnapshot
┌──────────────▼───────────────┐   ┌──────────────────────────────┐
│   RL Environment (M3)        │   │   Benchmarks (M3)            │
│   StateBuilder               │◀──│   StressNg / Sysbench /      │
│   ActionMapper               │   │   Hackbench / Cyclictest /   │
│   RewardShaper               │   │   Fio adapters               │
│   LinuxSchedulerEnv          │   └──────────────────────────────┘
└──────────────┬───────────────┘
               │ apply_parameters()
┌──────────────▼───────────────┐   ┌──────────────────────────────┐
│   Scheduler Controller (M2)  │   │   Safety (M2/M3)             │
│   ParameterRegistry          │◀──│   SecondaryValidator         │
│   Validator → Writer         │   │   Watchdog (rollback thread) │
│   RollbackStack              │   │   CheckpointManager          │
│   ProfileStore               │   └──────────────────────────────┘
└──────────────────────────────┘
               │ sysctl write / readback
     ┌─────────▼──────────┐
     │  Linux Kernel       │
     │  /proc/sys/kernel/  │
     └────────────────────┘
               │
┌──────────────▼───────────────┐
│   Trainer (M4)               │
│   PPO / SAC (SB3)            │
│   SchedulerCheckpointCallback│
│   TrainingResult             │
└──────────────────────────────┘
```

---

## Module Map

| Directory        | Milestone | Purpose |
|-----------------|-----------|---------|
| `monitor/`       | M1        | `/proc` readers → `SystemSnapshot` |
| `storage/`       | M1+       | SQLite backend for snapshots, benchmark results, applied configs |
| `scheduler/`     | M2        | Safe kernel parameter write/verify/rollback pipeline |
| `safety/`        | M2        | `SecondaryValidator`, `Watchdog`, `CheckpointManager` |
| `benchmarks/`    | M3        | Pluggable benchmark adapters (`stress-ng`, `sysbench`, `hackbench`, `cyclictest`, `fio`) |
| `rl/`            | M3        | `StateBuilder`, `ActionMapper`, `RewardShaper`, `LinuxSchedulerEnv` |
| `core/`          | M4        | `Trainer` (PPO/SAC), `EpisodeRunner`, checkpoint callback |
| `dashboard/`     | M1–M4     | PyQt6 live performance dashboard |
| `config/`        | M1+       | YAML-driven experiment configuration |
| `scripts/`       | M1–M4     | Entry-point scripts for each milestone |
| `tests/`         | M1–M4     | Unit and failure-injection tests (no root required) |

---

## Quick Start

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# GUI only:
pip install PyQt6 pyqtgraph
```

### 2. Launch the dashboard (includes AI Training Auto-Tuner)

```bash
python3 dashboard/app.py
```
Use the **White** and **Black** buttons in the top-right corner to change the
dashboard theme immediately. The selection is remembered for the next launch
and is also available under **Settings → Appearance**.

*Note: The new Auto-Tuner & Sweep panel is available in the dashboard. Use it to run coordinate descent parameter sweeps and view real-time training score curves.*

### 3. Run the Live Tuner Daemon (Headless)

```bash
python3 scripts/run_live_tuner.py --sweep-db data/sweep.db -v
```

### 4. Run a Parameter Sweep (Headless)

```bash
python3 scripts/run_sweep.py --workload gaming --steps 5 --db data/sweep.db
```

### 5. Run the test suite

```bash
python3 -m pytest tests/ -v
# No root or live kernel writes required
```

---

## Configuration

All components accept a YAML config file (see `config/`):

```bash
python3 scripts/run_benchmarks.py --config config/benchmarks.yaml
python3 scripts/run_monitor.py    --config config/monitor.yaml
```

See [`config/`](config/) for example files and the [config loader docs](docs/CONFIG.md).

---

## Milestone Docs

| Doc | Contents |
|-----|----------|
| [M1 — Monitor + Storage](docs/M1_README.md) | `/proc` sources, `SystemSnapshot`, SQLite |
| [M2 — Scheduler Controller](docs/M2_README.md) | `ParameterRegistry`, `Validator`, `Writer`, safety baseline |
| [M3 — RL Environment + Benchmarks](docs/M3_README.md) | `LinuxSchedulerEnv`, benchmark adapters, `RewardShaper` |
| [M4 — Trainer](docs/M4_README.md) | PPO/SAC training, checkpointing, evaluation |

---

## Recovery and safety

Parameter writes pass registry validation and, when supplied, the independent
secondary validator. Each write is read back. The controller serialises its
operations, restores failed transactions, retains failed recovery states for
retry, and blocks further tuning after a recovery failure.

RL episodes capture their initial baseline, restore all registered parameters at
reset/close, and seed relative actions from actual readbacks. The training, sweep and live-tuner CLIs persist a baseline checkpoint, runs a watchdog, and restores on success,
exceptions, Ctrl-C, or SIGTERM. Unresolved checkpoints block new training runs.
Live sessions also hold a host lease against cooperating controllers and validate
known RT/uclamp parameter relationships. `--supervised` enables a surviving parent
to attempt recovery if the training child dies.

```bash
python scripts/run_training.py --dry-run --timesteps 256 --eval-episodes 1 \
  --checkpoint-dir /tmp/scheduler-training
# Recover an interrupted live session using the same config and parameter subset:
python scripts/run_training.py --recover --config config/scheduler.yaml
```

Writes remain sequential kernel operations. A thread watchdog cannot recover from
process death or kernel hangs; persistent checkpoints support explicit recovery.
Use an isolated test host for live experiments. Read the
[recovery boundaries](docs/EVALUATION.md#recovery-boundaries) before live tuning.

## Measured comparisons

`scripts/run_evaluation.py` compares fixed configurations or adaptive model
inference against the captured baseline. Model mode includes a random-action
baseline. It randomises trial order, repeats measurements, and saves raw JSONL
and a JSON summary with variability and paired bootstrap intervals. Dry-run reports are
explicitly synthetic. Follow the [evaluation procedure](docs/EVALUATION.md) to
compare configurations selected by sweeps, random search, or training across
CPU, memory, mixed-load, and latency benchmark adapters. Read-only compatibility
checks are available through `scripts/check_host.py` and opt-in host tests.

Historical hardcoded slide figures are unverified examples, not evidence of
measured gains. Existing binary presentations have not been regenerated. The
maintained v7–v9 templates disclose illustrative comparison data and mark
unmeasured overhead/stability claims as pending.

## Tests

```bash
python -m pytest tests/ -q
```

Tests cover monitoring, storage, scheduler control, RL integration, training,
workload selection, sweeps, evaluation, partial writes, failed restoration,
interruption cleanup, and checkpoint recovery using fake backends.
Passing these tests does not establish real workload improvements.

---

## Project Structure

```
rl-scheduler-framework/
├── benchmarks/          # Benchmark adapters (stress-ng, sysbench, …)
├── config/              # YAML config loader + example configs
├── core/                # Trainer, EpisodeRunner, checkpoint callback
├── dashboard/           # PyQt6 GUI
│   └── panels/          # Overview, Processes, Memory, Scheduler panels
├── data/                # Runtime data (SQLite DBs, checkpoints) — git-ignored
├── docs/                # Per-milestone documentation
├── monitor/             # /proc readers → SystemSnapshot
├── rl/                  # RL environment components
├── safety/              # Watchdog, secondary validator, checkpoint manager
├── scheduler/           # Kernel parameter control pipeline
├── scripts/             # Entry-point CLIs
├── storage/             # SQLite storage backend
├── tests/               # Full unit test suite
└── utils/               # Shared utilities
```
