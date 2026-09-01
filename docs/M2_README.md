# M2 — Scheduler Controller + Safety Baseline

Status: **built and passing** (9 scheduler tests + 3 safety tests).

---

## What's here

### `scheduler/`

| File | Class / Symbol | Purpose |
|------|----------------|---------|
| `types.py` | `ParameterMeta` | Dataclass describing one tunable (name, type, bounds, sysctl path) |
| `exceptions.py` | `ValidationError`, `WriteError`, `ReadbackError`, … | Typed exception hierarchy |
| `registry.py` | `ParameterRegistry` | Central store for all registered tunables |
| `validator.py` | `Validator` | Type-checks and bounds-checks a `{name: value}` dict against the registry |
| `backend.py` | `SchedulerBackend` (ABC), `SysctlBackend` | Abstract write/read interface; `SysctlBackend` shells out to `sysctl -w` |
| `writer.py` | `Writer` | Calls the backend, then reads the value back to confirm the kernel accepted it |
| `rollback.py` | `RollbackStack` | LIFO stack of `{name: previous_value}` dicts; enables `controller.rollback()` |
| `profile.py` | `ProfileStore` | In-memory named parameter sets; `apply_profile()` delegates to `apply_parameters()` |
| `controller.py` | `SchedulerController` | Orchestrates validate → capture-current-state → write → push-rollback |

### `safety/`

| File | Class | Purpose |
|------|-------|---------|
| `validator.py` | `SecondaryValidator` | Hardcoded absolute limits independent of the registry — a second belt after the first |
| `watchdog.py` | `Watchdog` | Background thread; calls `rollback_callback()` if not `.ping()`-ed within `timeout_sec` |
| `checkpoint.py` | `CheckpointManager` | JSON snapshot of system state to `/tmp`; used for crash recovery on next startup |

---

## The write pipeline

```
controller.apply_parameters({"sched_min_granularity_ns": 5_000_000})
    │
    ├─ Validator.validate()            type=int ✓  100000 ≤ 5000000 ≤ 100000000 ✓
    │
    ├─ backend.read(current_value)     → push {"sched_min_granularity_ns": 3000000} onto RollbackStack
    │
    ├─ Writer.write_and_verify()
    │       ├─ SysctlBackend.write()   sysctl -w kernel.sched_min_granularity_ns=5000000
    │       └─ SysctlBackend.read()    sysctl -n kernel.sched_min_granularity_ns → "5000000" ✓
    │
    └─ logger.info("applied 1 parameters")
```

If the readback value doesn't match the written value, `ReadbackError` is raised before the rollback stack is updated, leaving the system in the pre-write state.

---

## Rollback

```python
controller.rollback()
# Pops the most recent snapshot from the RollbackStack and re-writes each value.
# If the stack is empty, logs a warning and returns safely.
```

The `Watchdog` wraps this: if the RL agent (or any caller) fails to call `wd.ping()` within `timeout_sec`, the watchdog thread calls `rollback_callback()` automatically — no human intervention needed.

---

## Registering a new parameter

```python
from scheduler import ParameterRegistry, ParameterMeta

reg = ParameterRegistry()
reg.register(ParameterMeta(
    name="sched_cfs_bandwidth_slice_us",
    type=int,
    min_value=1,
    max_value=100_000,
    backend="sysctl",
    path="kernel.sched_cfs_bandwidth_slice_us",
    description="CFS bandwidth slice per refill (µs)",
))
```

Any new `ParameterMeta` registered here is automatically picked up by:
- `Validator` (bounds enforcement)
- `Writer` (write/readback)
- `StateBuilder` in M3 (observation vector)
- `ActionMapper` in M3 (action space sizing)
- `SchedulerPanel` in the dashboard (parameter table)

---

## Running the demo

```bash
python3 scripts/run_scheduler.py
```

Uses a `DemoMockBackend` (in-memory dict) so no real sysctl writes happen. Demonstrates apply → rollback → profile apply → watchdog timeout.

---

## Test coverage

```
tests/test_scheduler.py  (9 tests)
  test_registry_register_and_get
  test_registry_get_not_found
  test_validator_valid
  test_validator_invalid_bounds
  test_validator_invalid_type
  test_writer_write_and_verify
  test_writer_readback_error
  test_controller_apply_and_rollback
  test_profile_store

tests/test_safety.py     (3 tests)
  test_secondary_validator
  test_watchdog
  test_checkpoint_manager
```

All tests use a `FakeBackend` (in-memory dict) — no root required.

---

## Known gaps / design notes

- `SysctlBackend` shells out to the `sysctl` binary. A direct `/proc/sys` write (like the dashboard's `_write_sysctl`) avoids the subprocess overhead and is preferred for the RL hot-loop. A `ProcSysBackend` is a natural extension.
- `ProfileStore` is currently in-memory only. For persistence across restarts, it should serialize to the SQLite `applied_config` table (see `storage/db.py`).
- `SecondaryValidator.hard_limits` contains only two parameters. Every parameter added to the dashboard's default registry should have a corresponding hard-limit entry here.

---

## Next

M3: RL Environment (`StateBuilder`, `ActionMapper`, `RewardShaper`, `LinuxSchedulerEnv`) + Benchmark adapters.
