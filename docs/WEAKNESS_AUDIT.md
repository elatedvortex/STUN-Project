# Weakness Audit — RL Scheduler Framework (M1–M4)

> **Date:** 2026-08-24  
> **Scope:** Full codebase review — every `.py` source file, all 67 tests, configs, scripts  
> **Rating Scale:** 🔴 Critical · 🟠 High · 🟡 Medium · 🔵 Low

---

## Summary Matrix

| # | Category | 🔴 | 🟠 | 🟡 | 🔵 |
|---|----------|:--:|:--:|:--:|:--:|
| 1 | Safety System Integrity | 2 | 1 | 1 | – |
| 2 | RL / Training Design | 1 | 2 | 2 | 1 |
| 3 | Persistence & Audit Trail | – | 2 | 1 | – |
| 4 | Testing Gaps | – | 2 | 2 | – |
| 5 | Architecture / Integration | 1 | 1 | 2 | – |
| 6 | Security & Hardening | – | 1 | 2 | – |
| 7 | Code Quality | – | – | 2 | 2 |
| 8 | Deployment Readiness | – | 1 | 1 | 1 |
| 9 | Documentation | – | – | 1 | 1 |
| **Total** | | **4** | **10** | **14** | **5** |

---

## 1 · Safety System Integrity

### 🔴 1.1 — SecondaryValidator is NEVER called in the write pipeline

The project report claims **"three independent validation layers."** In reality:

- **Layer 1** (`scheduler/validator.py` → `Validator`) ✅ Called by `SchedulerController.apply_parameters()`
- **Layer 2** (`safety/validator.py` → `SecondaryValidator`) ❌ **Not integrated anywhere in the write path**
- **Layer 3** (`safety/watchdog.py` → `Watchdog`) ✅ Works correctly

The `SecondaryValidator` exists, is tested, but is **never invoked** by the `SchedulerController`, the `Writer`, or the `LinuxSchedulerEnv`. The only caller is `scripts/run_scheduler.py` (a demo script), which calls it manually. The claim of "defence in depth" with three validation layers is therefore **inaccurate** in production paths.

**Impact:** A value passing `Validator` bounds but violating safety hard limits would reach the kernel unchecked.

```
# Searched the entire codebase — only callers:
scripts/run_scheduler.py:80    sec_validator = SecondaryValidator()   # demo script only
tests/test_safety.py:8         val = SecondaryValidator()             # test only
```

**File:** `scheduler/controller.py` — `apply_parameters()` has no `SecondaryValidator` call.

---

### 🔴 1.2 — CheckpointManager is NEVER called in the training loop

The `CheckpointManager` (`safety/checkpoint.py`) — designed for **crash recovery** of kernel parameter state — is instantiated only in demo scripts and tests. During actual training via `Trainer.train()` or `EpisodeRunner.run_episode()`, no kernel-state checkpoint is saved to disk.

If the process crashes mid-training (OOM, SIGKILL, power loss), there is **no way to recover the kernel's pre-training parameter state** because:

- The `RollbackStack` is in-memory only
- The `CheckpointManager` is never called
- The checkpoint defaults to `/tmp/` which is volatile

**Impact:** On a crash during real training, the kernel retains whatever parameters the agent last wrote — with no record of the original values.

**File:** `safety/checkpoint.py:10` — defaults to `/tmp/rl_scheduler_checkpoint.json`.

---

### 🟠 1.3 — Watchdog has a race condition on `_last_ping`

The `Watchdog._last_ping` field is read by the watchdog thread and written by the main thread (via `ping()`), but there is **no lock, no `threading.Event`, and no atomic operation**:

```python
# safety/watchdog.py:17-18
def ping(self) -> None:
    self._last_ping = time.time()    # main thread writes

# safety/watchdog.py:36
if time.time() - self._last_ping > self.timeout_sec:   # bg thread reads
```

On CPython, the GIL makes this *practically* safe for simple float assignments, but:

- It's not guaranteed by the Python specification
- On alternative runtimes (PyPy, GraalPy, or future no-GIL Python 3.13+), this is a data race
- The `_running` flag has the same issue

**File:** `safety/watchdog.py`

---

### 🟡 1.4 — SecondaryValidator only covers 2 of 8 parameters

Even if integrated, `SecondaryValidator.hard_limits` only defines limits for:

- `kernel.sched_min_granularity_ns`
- `kernel.sched_wakeup_granularity_ns`

The project registers **8 tunable parameters** (see dashboard's `_build_default_registry()`). The other 6 — including `sched_rt_runtime_us` (which can disable RT throttling at `-1`) and `sched_autogroup_enabled` — have **no safety-layer coverage**.

**File:** `safety/validator.py:10-13`

---

## 2 · RL / Training Design

### 🔴 2.1 — Reward signal is near-zero under training with constant fake benchmarks

In `run_training.py`'s dry-run mode (which is the **only mode that works** due to `if args.dry_run or True`), the benchmark returns `score = 100.0 + random.gauss(0, 8)`. Since the EMA converges quickly to ~100.0, the normalised reward becomes:

```
normalised = (score - ema) / (|ema| + 1e-9) ≈ gauss(0, 8) / 100 ≈ ±0.08
```

This means the agent receives a nearly uniform `+0.1` (stability bonus) every step with tiny noise — **it learns nothing meaningful**, and `mean_reward ≈ 0.1` across all episodes regardless of policy quality.

**Impact:** Every dry-run training session produces a model that has learned nothing. The `TrainingResult.mean_reward` is essentially constant noise — it doesn't validate that the training infrastructure works.

**File:** `scripts/run_training.py:68-71`

---

### 🟠 2.2 — Observation doesn't include the action the agent just took

The observation vector (`rl/state.py`) contains system metrics + current scheduler parameter values. But in **discrete mode**, the agent's actions are *relative* (nudge up/down), and the observation only reflects the *post-write* parameter value — the agent doesn't see:

- Which action it took last step (for temporal credit assignment)
- A delta/velocity of parameter changes
- Any benchmark result from the previous step

This makes credit assignment harder for PPO. Standard RL practice would include the previous action and/or reward as part of the observation (especially for POMDPs or partially observable setups).

**File:** `rl/state.py`

---

### 🟠 2.3 — Benchmark runs on EVERY step — training is orders of magnitude slower than necessary

In `LinuxSchedulerEnv.step()`, the benchmark runs **every single step** (line 157):

```python
result = self._benchmark.run(**self._benchmark_kwargs)
```

With real benchmarks like stress-ng (5-second default timeout), a 20-step episode takes **100+ seconds**. A 50,000-timestep training run would take **~70 hours**. This is a fundamental architecture issue — most kernel-tuning research uses either:

- Simulated benchmarks during training (fast) + real evaluation
- Benchmark every N steps, not every step

**File:** `rl/env.py:157`

---

### 🟡 2.4 — Action mapper's discrete step size is fixed at 1/10th of range

The `ActionMapper` uses `n_steps=10` (default), meaning each discrete action nudges a parameter by 10% of its full range. For `sched_rt_period_us` (range: 1 to 1,000,000), that's a step of **100,000 µs** — which is a massive jump that could destabilise the scheduler. There's no adaptive step size, no annealing, and no finer-grained control.

**File:** `rl/action.py:38-39`

---

### 🟡 2.5 — RewardShaper EMA initialisation bias

On the very first benchmark call, the EMA is set to the first score:

```python
if self._ema_baseline is None:
    self._ema_baseline = score
```

This means `normalised = (score - score) / (|score| + 1e-9) = 0.0`, and the first reward is always `+λ_stability` (0.1). The agent gets a positive reward on its first step regardless of what it does.

**File:** `rl/reward.py:65-66`

---

### 🔵 2.6 — PPO n_steps=256 but episode_steps=20 → buffer never fills cleanly

In `run_training.py`, PPO is configured with `n_steps=256` (the rollout buffer size), but the episode length is 20 steps. This means PPO collects data across **~13 episodes** before each update. With a deterministic fake benchmark, this creates correlated samples across the buffer with near-identical returns — reducing learning signal quality.

**File:** `scripts/run_training.py:137`

---

## 3 · Persistence & Audit Trail

### 🟠 3.1 — applied_config audit trail is NEVER written

The SQLite schema has a well-designed `applied_config` table for tracking every sysctl write. The `write_applied_config()` method exists. But **it is never called anywhere**:

```
# grep for write_applied_config across entire codebase:
storage/db.py:226    def write_applied_config(    # definition only
```

The `SchedulerController.apply_parameters()` writes to sysctl but doesn't log to the database. This means the "full audit trail" described in the project report **doesn't exist in practice**.

**File:** `storage/db.py:226-257`

---

### 🟠 3.2 — TrainingResult is not persisted (acknowledged in report, still critical)

Training results, episode rewards, and hyperparameters are lost after each run. The checkpoint metadata JSON stores basic info, but there's no SQLite `training_run` table. Without this, you cannot:

- Compare training runs across seeds
- Plot learning curves from historical data
- Prove that the agent improved (thesis-critical)

**File:** `core/trainer.py:37-46`

---

### 🟡 3.3 — Benchmark results written only by `run_benchmarks.py`, not during training

`write_benchmark_result()` is called only in the `scripts/run_benchmarks.py` sweep script. During actual RL training (where benchmarks are run on every step), the results are **not persisted**. This means you can't reconstruct what the agent saw during training.

**File:** `storage/db.py:161`, `rl/env.py:157`

---

## 4 · Testing Gaps

### 🟠 4.1 — No integration tests — all tests use fakes

Every test uses `FakeBackend`, `FakeMonitor`, `FakeBenchmark`, or `_DryRunBackend`. There are **zero tests** that:

- Actually read from `/proc/stat` on a real system
- Use a real `SysctlBackend` (even in read-only mode)
- Run a real benchmark subprocess
- Test the `SchedulerController → Writer → SysctlBackend` pipeline end-to-end

This means the integration points (where most bugs live) are completely untested.

---

### 🟠 4.2 — Safety module has only 3 tests

The safety module — arguably the most critical module in a system that writes to kernel parameters — has the thinnest test coverage:

```
test_safety.py     3 tests
  - test_secondary_validator     (basic bounds check)
  - test_watchdog                (timeout fires)
  - test_checkpoint_manager      (save/load/clear)
```

Missing tests:

- Watchdog recovery when `rollback_callback` raises an exception
- Watchdog thread cleanup (join timeout, daemon behavior)
- CheckpointManager concurrent access
- SecondaryValidator edge cases (negative values, None, boundary values)
- **Integration test**: Watchdog + Controller rollback pipeline

**File:** `tests/test_safety.py`

---

### 🟡 4.3 — Tests use hardcoded paths to `/tmp`

```python
# test_safety.py:38
path = "/tmp/test_checkpoint.json"
```

This creates test artifacts in `/tmp` that aren't cleaned up on failure, and conflicts with parallel test runs. Should use `tmp_path` pytest fixture.

**File:** `tests/test_safety.py:38`

---

### 🟡 4.4 — No test for the training script itself

`run_training.py` is the primary user-facing entry point but has no integration test verifying it runs end-to-end. `test_trainer.py` tests the `Trainer` class in isolation but not the script's argparse, dry-run setup, or checkpoint-resume flow.

---

## 5 · Architecture / Integration

### 🔴 5.1 — Registry mismatch across modules

Three different places define different sets of tunable parameters:

| Location | Parameters |
|----------|-----------|
| `dashboard/app.py` `_build_default_registry()` | 8 params (rr_timeslice, rt_period, rt_runtime, cfs_bandwidth, autogroup, util_clamp_max, util_clamp_min, schedstats) |
| `scripts/run_training.py` `_make_registry()` | 2 params (min_granularity_ns, wakeup_granularity_ns) |
| `config/scheduler.yaml` | 4 params (rr_timeslice, rt_period, rt_runtime, autogroup) |
| `safety/validator.py` hard_limits | 2 params (min_granularity_ns, wakeup_granularity_ns) |

**These sets don't even overlap!** The training script trains on `sched_min_granularity_ns` and `sched_wakeup_granularity_ns`, but the dashboard monitors a completely different set of 8 parameters. The safety validator guards the training params, but the YAML config defines yet another set.

**Impact:** There is no single source of truth. Adding or removing a parameter requires editing 3-4 files manually — and missing one creates silent mismatches.

**Files:** `scripts/run_training.py:78-84`, `dashboard/app.py:52-131`, `config/scheduler.yaml`

---

### 🟠 5.2 — Config loader is not used by any script

The `config/loader.py` module has a well-structured `ExperimentConfig` system with YAML-driven configuration. However, **none of the scripts use it**:

- `run_training.py` → hardcodes everything via argparse
- `run_benchmarks.py` → parses YAML manually
- `run_monitor.py` → hardcodes defaults
- `run_dashboard.py` → hardcodes defaults

The config system is dead code in practice.

**File:** `config/loader.py`

---

### 🟡 5.3 — Two code-generation scripts committed to repo

`scheduler_setup.py` and `safety_setup.py` are one-time code generators that write out the scheduler and safety module files. They contain **hardcoded absolute paths** to the developer's home directory:

```python
base_dir = "/home/v0r73x/Documents/final/project/rl-scheduler-framework/scheduler"
```

These are development scaffolding that should have been removed after initial use. They serve no purpose now and expose the developer's filesystem layout.

**Files:** `scheduler_setup.py`, `safety_setup.py`

---

### 🟡 5.4 — `SysctlBackend` uses `subprocess.run` without timeout

Both `write()` and `read()` in `SysctlBackend` call `subprocess.run()` without a `timeout` parameter. If sysctl hangs (rare but possible on a locked-up system), the entire training pipeline blocks indefinitely — the watchdog can't help because the main thread is stuck in a blocking subprocess call.

**File:** `scheduler/backend.py:16-37`

---

## 6 · Security & Hardening

### 🟠 6.1 — No input sanitisation on sysctl path strings

The `SysctlBackend.write()` constructs a shell command from user-controlled strings:

```python
subprocess.run(["sysctl", "-w", f"{path}={value}"], ...)
```

While `subprocess.run()` with a list (not `shell=True`) mitigates shell injection, the `path` and `value` are ultimately derived from the `ParameterRegistry` and `ActionMapper` — which in turn come from configuration. A malformed YAML config could inject unexpected sysctl paths. Defence: the `Validator` checks values but **never validates that the path is a legitimate sysctl key**.

**File:** `scheduler/backend.py:18-23`

---

### 🟡 6.2 — CheckpointManager uses world-readable `/tmp` by default

Checkpoint files containing kernel parameter state are written to `/tmp/rl_scheduler_checkpoint.json` with no permission control. Any user on the system can read (and potentially tamper with) the checkpoint, which could be used to force a malicious rollback state.

**File:** `safety/checkpoint.py:10`

---

### 🟡 6.3 — No capability check before attempting sysctl writes

The framework doesn't verify it has `CAP_SYS_ADMIN` or root privileges before attempting to write. It just tries and catches `subprocess.CalledProcessError`. A better UX would be to check permissions at startup and fail fast with a clear error message.

**File:** `scheduler/backend.py`

---

## 7 · Code Quality

### 🟡 7.1 — Inconsistent error handling in env.step()

```python
# rl/env.py:152
except (ValidationError, Exception) as exc:
```

Catching `(ValidationError, Exception)` is redundant — `Exception` already covers `ValidationError`. This suggests the developer intended to handle validation errors differently but then fell back to a blanket catch. The issue is that **any** exception (including bugs, `AttributeError`, `TypeError`) is silently swallowed and reported as a "rollback_triggered" — masking real errors during training.

**File:** `rl/env.py:152`

---

### 🟡 7.2 — `Trainer.load()` bypasses `__init__`

```python
# core/trainer.py:183-185
instance = cls.__new__(cls)
instance._algorithm_name = algorithm
instance._checkpoint_dir = Path("data/checkpoints")  # hardcoded!
```

This `cls.__new__` pattern is fragile — if `__init__` adds new fields, `load()` will silently produce instances with missing attributes. The hardcoded `data/checkpoints` path is also noted in the project report as a known gap.

**File:** `core/trainer.py:183-185`

---

### 🔵 7.3 — f-strings in logging calls

Multiple modules use f-strings in logger calls:

```python
logger.info(f"Successfully applied {len(params)} parameters.")
logger.error(f"Watchdog timeout ({self.timeout_sec}s)! Forcing rollback.")
```

This evaluates the string even when the log level is disabled. Should use `%`-style formatting:

```python
logger.info("Successfully applied %d parameters.", len(params))
```

Minor performance issue, but it's in hot paths (controller, watchdog).

---

### 🔵 7.4 — Unused imports in scheduler module

```python
# scheduler/backend.py:3
from typing import Any, Dict, List   # Dict and List are unused
```

Minor but present across several files. A `ruff` or `flake8` pass would catch these.

---

## 8 · Deployment Readiness

### 🟠 8.1 — `run_training.py` hard-codes `or True` — training NEVER uses real sysctl

```python
# scripts/run_training.py:114
if args.dry_run or True:  # always safe backend in scripts
```

This means `--dry-run` flag is meaningless — the script **always** uses the fake backend. To run real training, a developer must edit source code. This is documented as a known gap, but it makes the entire M4 trainer unable to prove its core value proposition (tuning real kernel parameters).

**File:** `scripts/run_training.py:114`

---

### 🟡 8.2 — No requirements pinning

`requirements.txt` uses loose version bounds (`>=`). Stable-Baselines3, Gymnasium, and PyTorch are fast-moving ecosystems. A future `pip install` could pull incompatible versions. Should use a lockfile (`pip freeze > requirements-lock.txt` or `poetry.lock`).

**File:** `requirements.txt`

---

### 🔵 8.3 — No `pyproject.toml` or `setup.py`

The project has no packaging metadata. You can't `pip install -e .` for development, which means `sys.path.insert(0, ...)` hacks are needed in every script (as seen in `run_training.py:24`).

---

## 9 · Documentation

### 🟡 9.1 — PROJECT_REPORT.md overclaims safety architecture

Section 2 states: *"No value reaches the kernel without passing through three independent validation layers."* As shown in §1.1 above, only **one** validation layer (the primary `Validator`) is actually in the write path. The report should be corrected to avoid credibility issues during evaluation/defence.

**File:** `PROJECT_REPORT.md`

---

### 🔵 9.2 — M4_README.md references different params than actual code

The M4_README examples show `n_steps=256, batch_size=64, n_epochs=4`, which matches `run_training.py`. But the params trained on (`sched_min_granularity_ns`, `sched_wakeup_granularity_ns`) are different from the 8 params described in the project report's tunable parameters table. This creates confusion about what the system actually tunes.

**File:** `docs/M4_README.md`

---

## Top 5 Priorities to Fix

| Rank | Issue | Severity | Effort |
|------|-------|----------|--------|
| 1 | **Integrate `SecondaryValidator` into write pipeline** (§1.1) | 🔴 Critical | ~1 hour |
| 2 | **Single source of truth for parameter registry** (§5.1) | 🔴 Critical | ~3 hours |
| 3 | **Wire `CheckpointManager` into training loop** (§1.2) | 🔴 Critical | ~2 hours |
| 4 | **Persist applied_config audit trail** (§3.1) | 🟠 High | ~1 hour |
| 5 | **Remove `or True` and add proper dry-run/live switching** (§8.1) | 🟠 High | ~1 hour |

These 5 fixes alone would address the project's most damaging structural weaknesses — the ones that would be immediately noticed by a reviewer or examiner.
