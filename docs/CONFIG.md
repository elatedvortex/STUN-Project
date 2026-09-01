# Config — YAML-Driven Experiment Configuration

All scripts in this project accept a `--config <path>` argument pointing to a YAML file that controls their behaviour. This avoids hard-coded parameters in source files and makes experiments reproducible.

---

## Quick start

```bash
# Generate all example configs in one step
python3 scripts/run_benchmarks.py --init-config

# Then edit config/benchmarks.yaml and run
python3 scripts/run_benchmarks.py --config config/benchmarks.yaml -v
```

---

## Schema

### `config/monitor.yaml`

```yaml
monitor:
  interval_sec: 1.0           # poll frequency
  db_path: data/monitor.db    # SQLite output
  duration_sec: null          # null = run forever; 60 = stop after 60 s
  sched_param_keys:
    - kernel.sched_rr_timeslice_ms
    - kernel.sched_rt_period_us
    - kernel.sched_rt_runtime_us
```

### `config/benchmarks.yaml`

```yaml
benchmarks:
  db_path: data/benchmarks.db
  repeats: 3                  # how many times to run each adapter

  adapters:
    - name: stress-ng
      enabled: true
      tag: baseline            # optional label written to benchmark_result.tag
      kwargs:
        timeout: 5
        workers: 2

    - name: sysbench
      enabled: true
      kwargs:
        timeout: 5
        threads: 2

    - name: hackbench
      enabled: true
      kwargs:
        groups: 1
        loops: 100

    - name: cyclictest
      enabled: false           # needs root + rt-tests package
      kwargs:
        loops: 1000

    - name: fio
      enabled: false           # writes to disk
      kwargs:
        size: 10M
```

### `config/scheduler.yaml`

```yaml
scheduler:
  params:
    - name: sched_rr_timeslice_ms
      path: kernel.sched_rr_timeslice_ms
      type: int
      min_value: 1
      max_value: 2000
      description: Round-Robin scheduler timeslice (ms)

    - name: sched_rt_period_us
      path: kernel.sched_rt_period_us
      type: int
      min_value: 1
      max_value: 1000000
      description: RT scheduling period (µs)
```

---

## Python API

```python
from config import load_config, save_default_configs

# Load
cfg = load_config("config/benchmarks.yaml")

# Access typed fields
print(cfg.benchmarks.repeats)             # 3
print(cfg.benchmarks.adapters[0].name)   # "stress-ng"

# Generate example files
save_default_configs("config/")
```

`load_config` returns an `ExperimentConfig` with three sub-configs:
- `cfg.monitor`    → `MonitorConfig`
- `cfg.benchmarks` → `BenchmarkConfig` (list of `BenchmarkAdapterConfig`)
- `cfg.scheduler`  → `SchedulerConfig` (list of `SchedulerParamConfig`)

---

## Dependency

The config loader requires **PyYAML**:

```bash
pip install pyyaml
```

If PyYAML is not installed, `load_config()` returns an `ExperimentConfig` with all defaults and emits a `RuntimeWarning`. Scripts remain functional — they just ignore the YAML file.

---

## CLI overrides

Most CLI flags override specific config values without editing YAML:

| Script | Flag | Overrides |
|--------|------|-----------|
| `run_benchmarks.py` | `--db` | `benchmarks.db_path` |
| `run_benchmarks.py` | `--repeats` | `benchmarks.repeats` |
| `run_benchmarks.py` | `--only stress-ng` | filters adapter list |
| `run_benchmarks.py` | `--tag post-tuning` | `BenchmarkAdapterConfig.tag` |
| `run_monitor.py` | `--db` | `monitor.db_path` |
| `run_monitor.py` | `--interval` | `monitor.interval_sec` |
| `run_monitor.py` | `--duration` | `monitor.duration_sec` |
