# Project Report — Adaptive RL Framework for Linux Scheduler Optimisation

> **Author:** v0r73x
> **Date:** August 2026
> **Status:** Core framework complete (M1–M4) · Next phase: production hardening & evaluation

---

## 1 · What Is This Project?

This project is a **research-grade framework** that uses **Reinforcement Learning** (PPO and SAC, via Stable-Baselines3) to **autonomously tune Linux kernel scheduler parameters** in real time, with the goal of maximising system throughput or minimising latency — without human intervention.

Instead of an administrator manually tweaking sysctl knobs like `sched_rt_period_us` or `sched_cfs_bandwidth_slice_us`, an RL agent:

1. **Observes** the current system state (CPU utilisation, load average, memory pressure, context switches, per-parameter kernel values).
2. **Decides** which scheduler parameter to nudge up, nudge down, or leave alone.
3. **Acts** by writing the new value to the kernel via a safe, validated pipeline.
4. **Measures** the outcome by running a benchmark (stress-ng, sysbench, hackbench, cyclictest, or fio).
5. **Learns** from the reward signal — improving over hundreds of episodes until it converges on a near-optimal configuration for the given workload.

The entire loop is wrapped in a **defence-in-depth safety system** — three layers of validation, automatic rollback on failure, and a watchdog thread that forcefully restores the kernel state if the agent hangs.

---

## 2 · What Has Been Built (Milestones M1–M4)

### M1 — System Monitor & Storage

| Component | Description |
|-----------|-------------|
| **`monitor/sources.py`** | Readers for `/proc/stat`, `/proc/meminfo`, `/proc/loadavg`, `/proc/cpufreq`, sysctl scheduler params, NUMA topology, and per-process samples |
| **`monitor/collector.py`** | `Monitor` class that aggregates all sources into a single `SystemSnapshot` every tick |
| **`monitor/types.py`** | `SystemSnapshot` dataclass — the universal data structure flowing through the entire framework |
| **`storage/db.py`** | SQLite backend with tables for `snapshot`, `benchmark_result`, and `applied_config` — full audit trail |

**Key design decision:** Every data source is a pluggable function `() → dict`. The `Monitor` collects them all into one flat snapshot, making it trivial to add new sources (e.g., GPU telemetry) without changing downstream code.

### M2 — Scheduler Controller & Safety

| Component | Description |
|-----------|-------------|
| **`scheduler/registry.py`** | `ParameterRegistry` — declares every tunable parameter (name, sysctl path, type, min, max) |
| **`scheduler/validator.py`** | `Validator` — type-checks and bounds-checks before any write |
| **`scheduler/writer.py`** | `Writer` — writes via sysctl and **reads back** to confirm the kernel accepted the value |
| **`scheduler/rollback.py`** | `RollbackStack` — stores previous values before every write for instant rollback |
| **`scheduler/controller.py`** | `SchedulerController` — orchestrates validate → write → verify → push-rollback |
| **`safety/validator.py`** | `SecondaryValidator` — independent hard limits (safety belt) |
| **`safety/watchdog.py`** | `Watchdog` — background thread that forces rollback if the agent doesn't ping within `timeout_sec` |
| **`safety/checkpoint.py`** | `CheckpointManager` — persists full parameter snapshots to disk for crash recovery |

**Key design decision:** No value reaches the kernel without passing through three independent validation layers. Every successful write is immediately read back to catch kernel-side rejections (e.g., clamped values).

### M3 — RL Environment & Benchmark Adapters

| Component | Description |
|-----------|-------------|
| **`rl/state.py`** | `StateBuilder` — converts `SystemSnapshot` → normalised `float32` observation vector (`[0,1]` range) |
| **`rl/action.py`** | `ActionMapper` — maps discrete or continuous gym actions → `{param_name: value}` dicts |
| **`rl/reward.py`** | `RewardShaper` — EMA-normalised delta reward with stability bonuses and rollback penalties |
| **`rl/env.py`** | `LinuxSchedulerEnv` — full Gymnasium-compliant environment (passes `check_env()`) |
| **`benchmarks/adapters.py`** | 5 benchmark adapters: stress-ng, sysbench, hackbench, cyclictest, fio |

**Key design decision:** The reward is *relative to a rolling EMA baseline*, not absolute. This keeps the reward signal stationary as the system drifts, giving the agent a clear gradient to follow.

### M4 — Trainer & Training Infrastructure

| Component | Description |
|-----------|-------------|
| **`core/trainer.py`** | `Trainer` — wraps SB3 PPO/SAC; exposes `train()`, `evaluate()`, `save()`, `load()`, `predict()` |
| **`core/checkpoint.py`** | `SchedulerCheckpointCallback` — saves `.zip` model + `_meta.json` every N steps |
| **`core/loop.py`** | `EpisodeRunner` — manual episode loop with watchdog lifecycle management |
| **`scripts/run_training.py`** | CLI entry point for training (supports dry-run, resume from checkpoint, algorithm selection) |

**Key design decision:** PPO with discrete actions is the recommended default — it's sample-efficient for small parameter spaces (2–8 params), and discrete actions produce a cleaner audit trail than continuous.

### Dashboard (Cross-Milestone)

A **PyQt6 live performance dashboard** (`dashboard/`) with four tabs:

- **Overview** — real-time CPU, memory, load graphs
- **Processes** — per-process resource consumption with stacked usage bars
- **Memory** — detailed memory breakdown
- **Scheduler** — live sysctl parameter values with manual override controls

---

## 3 · Current Architecture

```
                    ┌───────────────────────────────────────┐
                    │         Dashboard (PyQt6)             │
                    │  Overview │ Processes │ Memory │ Sched │
                    └──────────────┬────────────────────────┘
                                   │ SystemSnapshot (1 Hz)
      ┌────────────────────────────▼─────────────────────────┐
      │              Monitor (M1)                            │
      │  /proc/stat · /proc/meminfo · /proc/loadavg          │
      │  cpufreq · sysctl sched params · NUMA · processes    │
      └──────┬──────────────────────────────────┬────────────┘
             │                                  │
             │ SystemSnapshot                   │ → SQLite
             ▼                                  ▼
      ┌──────────────────┐             ┌──────────────────┐
      │  RL Environment  │             │  Storage Layer   │
      │  StateBuilder    │             │  snapshots       │
      │  ActionMapper    │◄────────────│  benchmark_runs  │
      │  RewardShaper    │             │  applied_configs │
      │  LinuxSchedEnv   │             └──────────────────┘
      └──────┬───────────┘
             │ apply_parameters()
             ▼
      ┌──────────────────┐   validate   ┌──────────────────┐
      │  Scheduler Ctrl  │◄────────────►│  Safety Layer    │
      │  Registry        │              │  SecondaryValid. │
      │  Validator       │              │  Watchdog thread │
      │  Writer          │              │  Checkpoint Mgr  │
      │  RollbackStack   │              └──────────────────┘
      └──────┬───────────┘
             │ sysctl write + readback
             ▼
      ┌──────────────────┐       ┌──────────────────┐
      │  Linux Kernel    │       │  Benchmarks      │
      │  /proc/sys/      │       │  stress-ng       │
      └──────────────────┘       │  sysbench        │
                                 │  hackbench       │
             ▲                   │  cyclictest      │
             │ score             │  fio             │
      ┌──────┴───────────┐      └──────────────────┘
      │  Trainer (M4)    │
      │  PPO / SAC (SB3) │
      │  Checkpoint CB   │
      └──────────────────┘
```

### Technology Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| RL Framework | Stable-Baselines3 2.3+ (PyTorch) |
| Gym Interface | Gymnasium 0.29+ |
| Dashboard | PyQt6 + pyqtgraph |
| Storage | SQLite (via `sqlite3` stdlib) |
| Configuration | YAML (via `PyYAML`) |
| Testing | pytest 8.0+ (67 tests, ~7 s, no root needed) |
| Kernel Interface | `/proc` filesystem + `sysctl` |

### Tunable Parameters (Default Registry)

| Parameter | Sysctl Path | Range | Description |
|-----------|-------------|-------|-------------|
| `sched_rr_timeslice_ms` | `kernel.sched_rr_timeslice_ms` | 1 – 2000 | Round-Robin timeslice |
| `sched_rt_period_us` | `kernel.sched_rt_period_us` | 1 – 1,000,000 | RT scheduling period |
| `sched_rt_runtime_us` | `kernel.sched_rt_runtime_us` | -1 – 1,000,000 | RT runtime within period |
| `sched_cfs_bandwidth_slice_us` | `kernel.sched_cfs_bandwidth_slice_us` | 1 – 100,000 | CFS bandwidth slice |
| `sched_autogroup_enabled` | `kernel.sched_autogroup_enabled` | 0 – 1 | Session auto-grouping |
| `sched_util_clamp_max` | `kernel.sched_util_clamp_max` | 0 – 1024 | UCLAMP upper bound |
| `sched_util_clamp_min` | `kernel.sched_util_clamp_min` | 0 – 1024 | UCLAMP lower bound |
| `sched_schedstats` | `kernel.sched_schedstats` | 0 – 1 | Schedstat collection |

---

## 4 · Test Coverage Summary

```
Module                Tests    Focus
─────────────────────────────────────────────────────────────
test_monitor.py        11     /proc readers, collector, snapshot assembly
test_scheduler.py       9     registry, validator, writer, controller pipeline
test_safety.py          3     secondary validator, watchdog, checkpoint manager
test_benchmarks.py      6     all 5 benchmark adapters + not-found handling
test_rl_env.py         25     StateBuilder, ActionMapper, RewardShaper, Env (+ check_env)
test_trainer.py        13     Trainer init/train/save/load/evaluate, checkpoint callback
─────────────────────────────────────────────────────────────
TOTAL                  67     All passing · ~7 seconds · No root / no kernel required
```

All tests use fakes/stubs — no real sysctl writes, no subprocess calls, no kernel dependency.

---

## 5 · Known Gaps in Current Implementation

| # | Gap | Impact | Severity |
|---|-----|--------|----------|
| 1 | `run_training.py` has `if args.dry_run or True` — real sysctl writes are hard-coded off | Cannot train on a live kernel without editing source | Low (safety feature) |
| 2 | `TrainingResult` is not persisted to SQLite | No historical record of training runs in the DB | Medium |
| 3 | `Trainer.load()` hard-codes `checkpoint_dir = "data/checkpoints"` | Can't load from arbitrary paths cleanly | Low |
| 4 | `RewardShaper` EMA is not shared across `Trainer` episodes | EMA resets may cause reward spikes at episode boundaries | Low |
| 5 | No multi-objective reward (e.g., throughput vs. latency trade-off) | Single-metric optimisation only | Medium |
| 6 | No curriculum learning / workload scheduling | Agent trains on one benchmark at a time | Medium |
| 7 | Dashboard has no RL training integration | Cannot visualise training progress in real time | Medium |

---

## 6 · Next Phase — Production Hardening & Evaluation (M5+)

The core framework (M1–M4) provides all the building blocks: monitoring, safe kernel control, a Gymnasium environment, and a PPO/SAC trainer. The next phase focuses on **closing the gap between a working prototype and a system you'd trust to run on real servers.**

### M5 — Experiment Pipeline & Reproducibility

**Goal:** Make it possible to run, record, compare, and reproduce full training experiments end-to-end.

| Deliverable | Description |
|-------------|-------------|
| **Experiment Runner** | A single CLI that takes a YAML experiment spec (algorithm, hyperparams, benchmark, episode count, seeds) and runs the full pipeline — monitor → env → train → evaluate → persist. |
| **Training History in SQLite** | Extend `storage/db.py` with a `training_run` table: algorithm, hyperparameters, per-episode reward curve, final evaluation metrics, model checkpoint path. |
| **Seed Control** | Ensure full determinism: env seed, numpy seed, torch seed, benchmark ordering — all controlled from config. |
| **Multi-Seed Sweeps** | Run the same experiment across N seeds and aggregate mean ± std reward curves to separate signal from noise. |
| **TensorBoard Integration** | Enable TensorBoard logging by default; write custom scalars for scheduler-specific metrics (rollback rate, parameter drift). |

### M6 — Multi-Workload Training & Curriculum Learning

**Goal:** Train agents that generalise across workload types, not just one benchmark.

| Deliverable | Description |
|-------------|-------------|
| **Workload Scheduler** | Rotate benchmarks within an episode or across episodes (round-robin, random, or difficulty-based curriculum). |
| **Multi-Objective Reward** | Composite reward that balances throughput, latency, and stability — with configurable weights. |
| **Workload-Conditioned Observations** | Add a workload-type indicator to the observation vector so the agent can learn workload-specific policies. |
| **Transfer Learning** | Pre-train on stress-ng → fine-tune on hackbench to evaluate cross-workload transfer. |

### M7 — Live Deployment Mode

**Goal:** Move from offline training to online, always-on optimisation on real servers.

| Deliverable | Description |
|-------------|-------------|
| **Online Training Loop** | Continuous training mode: the agent runs as a systemd service, collecting snapshots and nudging parameters in a background loop. |
| **Adaptive Safety Bounds** | Tighten/relax parameter bounds based on observed system stability (e.g., reduce exploration range during high-load periods). |
| **Anomaly Detection** | Monitor for abnormal system states (CPU spike > 95%, OOM risk) and auto-rollback before the watchdog timeout. |
| **Graceful Degradation** | If the agent's policy degrades (reward drops below baseline for K episodes), freeze parameters and alert. |
| **Systemd Unit File** | Production-ready `rl-scheduler.service` with restart policies, logging, and capability constraints (`CAP_SYS_ADMIN`). |

### M8 — Evaluation & Benchmarking Report

**Goal:** Produce a rigorous, publishable evaluation comparing RL-tuned parameters vs. Linux defaults vs. hand-tuned baselines.

| Deliverable | Description |
|-------------|-------------|
| **Baseline Profiles** | Capture default kernel parameters + 2-3 hand-tuned profiles (latency-optimised, throughput-optimised, balanced). |
| **A/B Evaluation Script** | Run each profile through the full benchmark suite (5 benchmarks × 3 runs × 3 seeds) and store results. |
| **Statistical Analysis** | Mean, std, confidence intervals, Wilcoxon signed-rank test for significance. |
| **Visualisation** | Matplotlib/Seaborn plots: reward curves, parameter trajectories over training, radar charts comparing profiles. |
| **Report Generator** | Auto-generate a PDF/Markdown evaluation report from SQLite data. |

### M9 — Dashboard v2 (Training Visualisation)

**Goal:** Integrate RL training visibility into the existing PyQt6 dashboard.

| Deliverable | Description |
|-------------|-------------|
| **Training Panel** | New dashboard tab showing live training metrics: episode reward, loss curves, parameter value trajectories. |
| **Policy Visualisation** | Heatmap of action probabilities across the parameter space. |
| **Experiment Browser** | Browse past training runs from SQLite, compare reward curves side-by-side. |
| **One-Click Training** | Start/stop/pause training from the GUI with parameter presets. |

---

## 7 · Recommended Next Steps (Priority Order)

```
Priority   Milestone   Effort    Description
────────────────────────────────────────────────────────────────────
  P0         M5        ~2 wk    Experiment pipeline + reproducibility
  P1         M8        ~1 wk    Baseline evaluation (validates the thesis)
  P2         M6        ~2 wk    Multi-workload training
  P3         M9        ~1 wk    Dashboard training panel
  P4         M7        ~3 wk    Live deployment mode
```

**Rationale:** M5 (experiment pipeline) is the highest priority because without reproducible experiments, you can't evaluate whether the RL agent actually outperforms Linux defaults — which is M8 (the thesis-validating milestone). M6 (multi-workload) is next because single-benchmark agents are a known limitation. M9 and M7 are nice-to-haves that make the system more impressive but aren't strictly required for the research contribution.

---

## 8 · How to Run Everything Today

```bash
# 1. Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install PyQt6 pyqtgraph   # for the dashboard

# 2. Run tests (no root needed)
python3 -m pytest tests/ -v   # 67 tests, ~7 seconds

# 3. Live system monitor (30 seconds)
python3 scripts/run_monitor.py --duration 30 --interval 1.0 --db data/monitor.db -v

# 4. Dashboard
python3 scripts/run_dashboard.py
# With live sysctl writes (requires root):
sudo python3 scripts/run_dashboard.py --with-scheduler

# 5. Benchmark sweep
python3 scripts/run_benchmarks.py --db data/benchmarks.db -v

# 6. Dry-run training (safe, no kernel writes)
python3 scripts/run_training.py --dry-run --timesteps 1000

# 7. Full training (requires root + benchmark tools)
sudo python3 scripts/run_training.py --algorithm ppo --timesteps 50000 --checkpoint-freq 5000
```

---

*This document was generated on 2026-08-09. For per-milestone details, see the `docs/` directory.*
