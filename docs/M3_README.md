# M3 — RL Environment + Benchmark Adapters

Status: **built and passing** (25 RL env tests + 6 benchmark adapter tests).

---

## What's here

### `rl/`

| File | Class | Purpose |
|------|-------|---------|
| `state.py` | `StateBuilder` | Converts a `SystemSnapshot` → normalised `np.float32` observation vector |
| `action.py` | `ActionMapper` | Maps a gym action (discrete int or continuous float array) → `{param_name: value}` |
| `reward.py` | `RewardShaper` | Converts a `BenchmarkResult` → scalar reward using EMA-normalised delta + bonuses/penalties |
| `env.py` | `LinuxSchedulerEnv` | Gymnasium-compatible env tying monitor, controller, benchmark, state, action, reward together |

### `benchmarks/`

| File | Adapter | Workload type | Primary metric | Higher is better? |
|------|---------|---------------|----------------|-------------------|
| `adapters.py` | `StressNgAdapter` | CPU | bogo-ops/sec | ✅ yes |
| `adapters.py` | `SysbenchAdapter` | Memory | ops/sec | ✅ yes |
| `adapters.py` | `HackbenchAdapter` | Scheduler latency | time (s) | ❌ no |
| `adapters.py` | `CyclictestAdapter` | RT latency | max latency (µs) | ❌ no |
| `adapters.py` | `FioAdapter` | I/O | write IOPS | ✅ yes |

All adapters implement `BenchmarkRunner.run(**kwargs) -> BenchmarkResult` and handle `FileNotFoundError` gracefully (tool not installed → `success=False, score=0.0`).

---

## Observation space

`StateBuilder` produces a flat `float32` vector of length `6 + n_params`:

| Index | Field | Normalisation |
|-------|-------|---------------|
| 0 | `cpu_util_pct` | ÷ 100 |
| 1 | `load_avg_1` | ÷ max(ncpus, 1) * 4 |
| 2 | `mem_util_pct` | ÷ 100 |
| 3 | `ctxt_switches_delta` | ÷ 1 000 000 |
| 4 | `runnable_procs` | ÷ 512 |
| 5 | `load_avg_5` | ÷ max(ncpus, 1) * 4 |
| 6…6+n | one slot per registered parameter | (value − min) ÷ (max − min) |

`None` fields (unavailable sources) map to `0.0`. All values are clipped to `[0, 1]`.

---

## Action space

### Discrete mode (default — works with PPO)

```
n_actions = 1 + 2 * n_params
```

| Action | Effect |
|--------|--------|
| 0 | no-op |
| 1 … n_params | increment parameter i by one step |
| n_params+1 … 2*n_params | decrement parameter i by one step |

Step size = `(max − min) / n_steps` (default `n_steps=10`). Values are clipped to `[min, max]`.

### Continuous mode (required for SAC)

Action vector ∈ `[-1, 1]^n_params`. Each component is linearly mapped to `[min, max]` and cast to the parameter type.

---

## Reward shaping

```
effective_score = score  if higher_is_better
                = -score otherwise   (invert lower-is-better metrics)

delta = effective_score - EMA_baseline
normalised_delta = delta / (|EMA_baseline| + ε)    (avoid div/0)

reward = normalised_delta
       + λ_stability   (if no rollback this step)
       - λ_penalty     (if rollback was triggered)
       = -1.0          (if benchmark failed)
```

Defaults: `ema_alpha=0.1`, `λ_stability=0.05`, `λ_penalty=0.2`, `ε=1.0`.

The EMA baseline tracks the rolling average score, so the agent is rewarded for *improvement* relative to its own history, not for absolute performance. This makes the reward signal stationary even as kernel state drifts.

---

## Environment lifecycle

```
env.reset()
  └── monitor.read_snapshot()           → initial obs
  └── RewardShaper.reset()              → clear EMA baseline
  └── returns (obs, {"step": 0})

env.step(action)
  ├── ActionMapper.decode(action)       → params dict (or {} for noop)
  ├── controller.apply_parameters()     → write to kernel (or rollback on error)
  ├── monitor.read_snapshot()           → new obs
  ├── benchmark.run()                   → BenchmarkResult
  ├── RewardShaper.shape()              → scalar reward
  └── returns (obs, reward, terminated, truncated, info)
      info keys: benchmark, params_applied, rollback_triggered, step
```

`terminated=True` when `step >= episode_steps`. `truncated` is always `False`.

---

## Gymnasium compliance

```python
from gymnasium.utils.env_checker import check_env
env, _ = _make_env(episode_steps=3)
check_env(env, skip_render_check=True)   # passes ✓
```

---

## Running a standalone benchmark sweep

```bash
python3 scripts/run_benchmarks.py --db data/benchmarks.db -v
# or with a config file:
python3 scripts/run_benchmarks.py --config config/benchmarks.yaml
```

Results are stored in the `benchmark_result` table in the SQLite DB. See `storage/db.py`.

---

## Test coverage

```
tests/test_benchmarks.py  (6 tests)
  test_stress_ng_adapter_success
  test_sysbench_adapter_success
  test_hackbench_adapter_success
  test_cyclictest_adapter_success
  test_fio_adapter_success
  test_adapter_not_found

tests/test_rl_env.py      (25 tests)
  TestStateBuilder         (4 tests)
  TestActionMapper         (7 tests)
  TestRewardShaper         (5 tests)
  TestLinuxSchedulerEnv    (8 tests — includes gymnasium check_env)
```

---

## Known gaps / design notes

- `CyclictestAdapter` requires the `rt-tests` package and root (to set SCHED_FIFO). On non-root systems it fails gracefully with `success=False`.
- `FioAdapter` writes a temporary file during benchmarking. The default `size="100M"` is safe for a quick sweep; increase to `"1G"` for more accurate I/O measurements.
- The `RewardShaper` EMA is reset on every `env.reset()`. For multi-episode continuity in evaluation mode, consider persisting the EMA baseline across resets.
- `ProcessSampleSource` in M1 does not take a true random sample of PIDs — see M1 README.

---

## Next

M4: Trainer (PPO/SAC via Stable-Baselines3), checkpoint callback, training entry-point script.
