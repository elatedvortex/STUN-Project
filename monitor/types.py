"""
Core data contracts for the monitor module.

Every downstream module (classifier, RL state builder, dashboard) consumes
SystemSnapshot and nothing else — this is the seam described in the
architecture doc, Section 3.1. Lock this schema before extending sources.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class ProcessInfo:
    """Per-process scheduling info, used by workload classification later."""
    pid: int
    comm: str
    state: str
    utime: int          # user-mode ticks
    stime: int          # kernel-mode ticks
    num_threads: int
    starttime: int | None = None  # /proc start ticks distinguish reused PIDs
    cpu_ticks_delta: int | None = None  # interval ticks; None for legacy samples


@dataclass(frozen=True)
class SystemSnapshot:
    """Immutable, normalized view of system state at one point in time.

    Fields default to None when their source was unavailable on this
    machine/kernel (see MetricSource.is_available()) — consumers must handle
    None rather than assuming every field is populated.
    """
    timestamp: datetime

    # CPU / scheduler
    cpu_util_pct: float | None = None
    ctxt_switches_total: int | None = None
    ctxt_switches_delta: int | None = None          # since previous snapshot
    load_avg_1: float | None = None
    load_avg_5: float | None = None
    load_avg_15: float | None = None
    runnable_procs: int | None = None
    total_procs: int | None = None

    # Memory
    mem_total_kb: int | None = None
    mem_available_kb: int | None = None
    mem_util_pct: float | None = None
    swap_total_kb: int | None = None
    swap_free_kb: int | None = None

    # CPU frequency (per-core average, MHz) — None if cpufreq not exposed
    cpu_freq_mhz: float | None = None

    # Scheduler tunables currently in effect (sysctl-backed) — empty dict if
    # the backend/keys aren't available on this kernel
    sched_params: dict[str, float] = field(default_factory=dict)

    # NUMA — empty tuple if no NUMA topology exposed
    numa_nodes: tuple[str, ...] = field(default_factory=tuple)

    # A capped sample ranked by recent CPU activity. The source scans process
    # counters before selecting this sample; cost scales with process count.
    processes: tuple[ProcessInfo, ...] = field(default_factory=tuple)

    # Which sources actually contributed to this snapshot — makes "None means
    # unavailable, not zero" auditable rather than silent
    available_sources: tuple[str, ...] = field(default_factory=tuple)

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)
