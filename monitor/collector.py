"""
Monitor / Collector — assembles registered MetricSources into SystemSnapshot
objects on demand.

This is the only class downstream modules (classifier, RL state builder,
dashboard) are expected to talk to for live system state. It owns the
capability-detection pass at startup (architecture doc, Section 3.1) so a
missing source (no cpufreq, no NUMA, no perf) degrades a snapshot's fields
to None instead of crashing the pipeline.
"""

from __future__ import annotations

import logging

from monitor.sources import (
    CpuFreqSource,
    MetricSource,
    NumaSource,
    ProcessSampleSource,
    ProcLoadAvgSource,
    ProcMemInfoSource,
    ProcStatSource,
    SysctlSchedSource,
)
from monitor.types import ProcessInfo, SystemSnapshot

logger = logging.getLogger(__name__)


def default_sources(sched_param_keys: tuple[str, ...] = ()) -> list[MetricSource]:
    """The standard source set used by M1. perf_stat is deliberately excluded
    by default — it's expensive and permission-sensitive; enable it
    explicitly if you want cache-miss data.
    """
    return [
        ProcStatSource(),
        ProcLoadAvgSource(),
        ProcMemInfoSource(),
        CpuFreqSource(),
        NumaSource(),
        SysctlSchedSource(keys=sched_param_keys),
        ProcessSampleSource(sample_size=25),
    ]


class Monitor:
    def __init__(self, sources: list[MetricSource] | None = None) -> None:
        self._all_sources = sources if sources is not None else default_sources()
        self._active_sources: list[MetricSource] = []
        self._capability_checked = False

    def check_capabilities(self) -> dict[str, bool]:
        """Runs each source's is_available() once and remembers the result.
        Call this at startup; read() uses the cached result rather than
        re-checking every tick.
        """
        report: dict[str, bool] = {}
        self._active_sources = []
        for source in self._all_sources:
            try:
                available = source.is_available()
            except Exception as exc:  # noqa: BLE001 - a source must never
                # take down startup; log and treat as unavailable
                logger.warning(
                    "capability check for %s raised %s — treating as unavailable",
                    source.name,
                    exc,
                )
                available = False
            report[source.name] = available
            if available:
                self._active_sources.append(source)
        self._capability_checked = True
        logger.info(
            "monitor capabilities: %s",
            ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in report.items()),
        )
        return report

    def read_snapshot(self) -> SystemSnapshot:
        if not self._capability_checked:
            self.check_capabilities()

        merged: dict = {}
        available_names: list[str] = []
        for source in self._active_sources:
            try:
                data = source.read()
            except Exception as exc:  # noqa: BLE001 - one bad source must not
                # break the whole snapshot
                logger.warning("%s.read() raised %s — skipping this tick", source.name, exc)
                continue
            if data:
                available_names.append(source.name)
                merged.update(data)

        processes = tuple(
            ProcessInfo(**p) for p in merged.pop("processes", ())
        )

        return SystemSnapshot(
            timestamp=SystemSnapshot.now(),
            processes=processes,
            available_sources=tuple(available_names),
            **{k: v for k, v in merged.items() if k in SystemSnapshot.__dataclass_fields__},
        )
