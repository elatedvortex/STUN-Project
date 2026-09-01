"""
config/loader.py — YAML-driven experiment configuration.

Usage
-----
    from config.loader import load_config, MonitorConfig, BenchmarkConfig

    cfg = load_config("config/benchmarks.yaml")
    print(cfg.benchmarks.adapters)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


# ---------------------------------------------------------------------------
# Config dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MonitorConfig:
    """Configuration for the system monitor (M1)."""
    interval_sec: float = 1.0
    db_path: str = "data/monitor.db"
    duration_sec: Optional[float] = None          # None = run forever
    sched_param_keys: List[str] = field(default_factory=lambda: [
        "kernel.sched_rr_timeslice_ms",
        "kernel.sched_rt_period_us",
        "kernel.sched_rt_runtime_us",
    ])


@dataclass
class BenchmarkAdapterConfig:
    """Configuration for one benchmark adapter invocation."""
    name: str                                    # adapter name, e.g. "stress-ng"
    enabled: bool = True
    kwargs: Dict[str, Any] = field(default_factory=dict)  # forwarded to adapter.run()
    tag: Optional[str] = None                   # label stored in the DB row


@dataclass
class BenchmarkConfig:
    """Top-level benchmark sweep configuration."""
    db_path: str = "data/benchmarks.db"
    repeats: int = 1                             # how many times to run each adapter
    adapters: List[BenchmarkAdapterConfig] = field(default_factory=list)


@dataclass
class SchedulerParamConfig:
    """One tunable parameter definition (mirrors ParameterMeta)."""
    name: str
    path: str
    type: str = "int"                            # "int" | "float"
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    description: str = ""
    backend: str = "sysctl"


@dataclass
class SchedulerConfig:
    """Configuration for the scheduler controller (M2)."""
    params: List[SchedulerParamConfig] = field(default_factory=list)


@dataclass
class ExperimentConfig:
    """Root config object loaded from a YAML file."""
    monitor: MonitorConfig = field(default_factory=MonitorConfig)
    benchmarks: BenchmarkConfig = field(default_factory=BenchmarkConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    # Raw dict for any keys not modelled above
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(path: str | Path) -> ExperimentConfig:
    """
    Load an ``ExperimentConfig`` from a YAML file.

    Falls back to all defaults if the file does not exist or yaml is not
    installed — so callers can always treat the return value as valid.

    Parameters
    ----------
    path : str | Path
        Path to the YAML config file.

    Returns
    -------
    ExperimentConfig
    """
    path = Path(path)
    if not path.exists():
        return ExperimentConfig()

    if not _YAML_AVAILABLE:
        import warnings
        warnings.warn(
            "PyYAML not installed — returning default config. "
            "Install with: pip install pyyaml",
            RuntimeWarning,
            stacklevel=2,
        )
        return ExperimentConfig()

    with open(path) as f:
        raw: Dict[str, Any] = yaml.safe_load(f) or {}

    cfg = ExperimentConfig()

    # ── monitor ──────────────────────────────────────────────────────────
    if "monitor" in raw:
        m = raw["monitor"]
        cfg.monitor = MonitorConfig(
            interval_sec=float(m.get("interval_sec", cfg.monitor.interval_sec)),
            db_path=str(m.get("db_path", cfg.monitor.db_path)),
            duration_sec=m.get("duration_sec"),
            sched_param_keys=m.get("sched_param_keys", cfg.monitor.sched_param_keys),
        )

    # ── benchmarks ───────────────────────────────────────────────────────
    if "benchmarks" in raw:
        b = raw["benchmarks"]
        adapters = [
            BenchmarkAdapterConfig(
                name=a["name"],
                enabled=bool(a.get("enabled", True)),
                kwargs=a.get("kwargs", {}),
                tag=a.get("tag"),
            )
            for a in b.get("adapters", [])
        ]
        cfg.benchmarks = BenchmarkConfig(
            db_path=str(b.get("db_path", cfg.benchmarks.db_path)),
            repeats=int(b.get("repeats", cfg.benchmarks.repeats)),
            adapters=adapters,
        )

    # ── scheduler ────────────────────────────────────────────────────────
    if "scheduler" in raw:
        s = raw["scheduler"]
        params = [
            SchedulerParamConfig(
                name=p["name"],
                path=p["path"],
                type=p.get("type", "int"),
                min_value=p.get("min_value"),
                max_value=p.get("max_value"),
                description=p.get("description", ""),
                backend=p.get("backend", "sysctl"),
            )
            for p in s.get("params", [])
        ]
        cfg.scheduler = SchedulerConfig(params=params)

    # Keep anything else
    cfg.extra = {k: v for k, v in raw.items() if k not in ("monitor", "benchmarks", "scheduler")}

    return cfg


# ---------------------------------------------------------------------------
# Registry builder (§5.1 — single source of truth)
# ---------------------------------------------------------------------------

def build_registry_from_config(
    config_path: str | Path = "config/scheduler.yaml",
    param_names: list[str] | None = None,
) -> "ParameterRegistry":
    """Build a ParameterRegistry from the YAML config file.

    This is the canonical way to construct a registry — all scripts,
    the dashboard, and the training loop should use this instead of
    defining parameters inline (§5.1).

    Parameters
    ----------
    config_path : str | Path
        Path to the scheduler YAML file.
    param_names : list[str] | None
        If given, only include parameters whose *name* appears in this
        list.  Useful for training on a subset of tunables.
    """
    from scheduler.registry import ParameterRegistry
    from scheduler.types import ParameterMeta

    _TYPE_MAP = {"int": int, "float": float}

    cfg = load_config(config_path)
    reg = ParameterRegistry()

    for p in cfg.scheduler.params:
        if param_names and p.name not in param_names:
            continue
        reg.register(ParameterMeta(
            name=p.name,
            type=_TYPE_MAP.get(p.type, int),
            min_value=p.min_value,
            max_value=p.max_value,
            description=p.description,
            backend=p.backend,
            path=p.path,
        ))

    return reg


def default_registry() -> "ParameterRegistry":
    """Convenience: load the full registry from the default scheduler.yaml."""
    return build_registry_from_config()


def save_default_configs(config_dir: str | Path = "config") -> None:
    """
    Write example YAML configs to *config_dir* if they don't already exist.
    Useful as a first-run bootstrap.
    """
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)
    _write_if_missing(config_dir / "monitor.yaml", _DEFAULT_MONITOR_YAML)
    _write_if_missing(config_dir / "benchmarks.yaml", _DEFAULT_BENCHMARK_YAML)
    _write_if_missing(config_dir / "scheduler.yaml", _DEFAULT_SCHEDULER_YAML)


def _write_if_missing(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content)


# ---------------------------------------------------------------------------
# Default YAML templates (written by save_default_configs)
# ---------------------------------------------------------------------------

_DEFAULT_MONITOR_YAML = """\
# Monitor configuration
monitor:
  interval_sec: 1.0
  db_path: data/monitor.db
  duration_sec: null          # null = run forever; set to e.g. 60 for a timed run
  sched_param_keys:
    - kernel.sched_rr_timeslice_ms
    - kernel.sched_rt_period_us
    - kernel.sched_rt_runtime_us
    - kernel.sched_cfs_bandwidth_slice_us
"""

_DEFAULT_BENCHMARK_YAML = """\
# Benchmark sweep configuration
benchmarks:
  db_path: data/benchmarks.db
  repeats: 3                  # run each adapter this many times

  adapters:
    - name: stress-ng
      enabled: true
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
      enabled: false          # requires root + rt-tests package
      kwargs:
        loops: 1000

    - name: fio
      enabled: false          # writes to disk — enable when appropriate
      kwargs:
        size: 10M
"""

_DEFAULT_SCHEDULER_YAML = """\
# Scheduler parameter registry configuration
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

    - name: sched_rt_runtime_us
      path: kernel.sched_rt_runtime_us
      type: int
      min_value: -1
      max_value: 1000000
      description: RT runtime within RT period (µs). -1 = unlimited

    - name: sched_autogroup_enabled
      path: kernel.sched_autogroup_enabled
      type: int
      min_value: 0
      max_value: 1
      description: Auto-group tasks by session (0=off, 1=on)
"""
