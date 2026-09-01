# Adaptive Reinforcement Learning Framework for Linux Scheduler Optimisation

A production-grade, safety-constrained framework that uses reinforcement learning (PPO/SAC via Stable-Baselines3) to autonomously tune Linux kernel scheduler parameters and optimise system throughput or latency.

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
| `tests/`         | M1–M4     | 67 unit tests (all passing, no root required) |

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

### 2. Run the live monitor

```bash
python3 scripts/run_monitor.py --duration 30 --interval 1.0 --db data/monitor.db -v
```

### 3. Launch the dashboard

```bash
python3 scripts/run_dashboard.py
# With root for live sysctl writes:
sudo python3 scripts/run_dashboard.py --with-scheduler
```

### 4. Run all benchmarks

```bash
python3 scripts/run_benchmarks.py --db data/benchmarks.db -v
```

### 5. Demo the scheduler controller

```bash
python3 scripts/run_scheduler.py
```

### 6. Run the test suite

```bash
python3 -m pytest tests/ -v
# 67 tests, ~7 seconds, no root, no kernel dependency
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

## Safety Design

The framework applies a **defence-in-depth** approach before any kernel parameter is touched:

```
ActionMapper.decode()
    │ (raw action → param dict)
    ▼
Validator.validate()          ← type check + min/max bounds from ParameterRegistry
    │
    ▼
SecondaryValidator.validate() ← independent hardcoded hard limits (safety belt)
    │
    ▼
Writer.write_and_verify()     ← write sysctl + readback confirms kernel accepted it
    │
    ▼
RollbackStack.push()          ← previous state saved before every write
    │
Watchdog thread               ← forces rollback if agent hangs > timeout_sec
```

No write reaches the kernel without passing all three validation layers. Every successful write is immediately read back to confirm the kernel accepted the value.

---

## Test Coverage

```
tests/test_monitor.py       — 11 tests  (M1: proc sources, collector, snapshot)
tests/test_scheduler.py     —  9 tests  (M2: registry, validator, writer, controller)
tests/test_safety.py        —  3 tests  (M2: secondary validator, watchdog, checkpoint)
tests/test_benchmarks.py    —  6 tests  (M3: all 5 benchmark adapters)
tests/test_rl_env.py        — 25 tests  (M3: StateBuilder, ActionMapper, RewardShaper, Env)
tests/test_trainer.py       — 13 tests  (M4: Trainer init/train/save/load/evaluate)
                              ─────────
                              67 total  (all passing, ~7 s)
```

All tests use fakes/stubs — **no root, no real kernel, no subprocess calls** reach the host.

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
