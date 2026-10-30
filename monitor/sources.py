"""
MetricSource implementations.

Each source wraps exactly one Linux interface (/proc/stat, /proc/loadavg,
etc.), does its own capability check, and returns a plain dict of readings.
The Collector (collector.py) is the only place these get assembled into a
SystemSnapshot — sources know nothing about each other or about the
snapshot schema.

This is deliberately defensive: reading kernel interfaces on the fly is
exactly the kind of code that segfaults a whole pipeline on one malformed
line if you're not careful, so every read is wrapped and every source
degrades to unavailable rather than raising into the Collector.
"""

from __future__ import annotations

import glob
import logging
import os
import re
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


class MetricSource(ABC):
    """One Linux interface, one source. Capability-checked once at startup;
    the Collector skips sources whose is_available() returns False rather
    than calling read() and hoping for the best on every tick.
    """

    name: str

    @abstractmethod
    def is_available(self) -> bool:
        """Cheap, side-effect-free check. Called once at Collector startup."""
        ...

    @abstractmethod
    def read(self) -> dict:
        """Return a flat dict of readings. Must not raise — on internal
        failure, log and return {} so one bad source doesn't take down a
        whole snapshot.
        """
        ...


class ProcStatSource(MetricSource):
    """CPU utilization (aggregate) and total context switches, from
    /proc/stat. Utilization is computed as a delta between successive reads,
    so this source is stateful (holds the previous jiffies sample).
    """
    name = "proc_stat"

    def __init__(self, path: str = "/proc/stat") -> None:
        self._path = Path(path)
        self._prev_total: int | None = None
        self._prev_idle: int | None = None
        self._prev_ctxt: int | None = None

    def is_available(self) -> bool:
        return self._path.exists()

    def read(self) -> dict:
        try:
            lines = self._path.read_text().splitlines()
        except OSError as exc:
            logger.warning("proc_stat: read failed: %s", exc)
            return {}

        result: dict = {}
        for line in lines:
            try:
                if line.startswith("cpu "):
                    fields = [int(x) for x in line.split()[1:]]
                    # user, nice, system, idle, iowait, irq, softirq, steal, ...
                    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)
                    total = sum(fields)
                    if self._prev_total is not None:
                        dt = total - self._prev_total
                        di = idle - self._prev_idle
                        result["cpu_util_pct"] = (
                            100.0 * (dt - di) / dt if dt > 0 else 0.0
                        )
                    self._prev_total, self._prev_idle = total, idle
                elif line.startswith("ctxt "):
                    ctxt = int(line.split()[1])
                    result["ctxt_switches_total"] = ctxt
                    if self._prev_ctxt is not None:
                        result["ctxt_switches_delta"] = ctxt - self._prev_ctxt
                    self._prev_ctxt = ctxt
                elif line.startswith("procs_running"):
                    result["runnable_procs"] = int(line.split()[1])
            except (ValueError, IndexError) as exc:
                # a single malformed line must not take down the whole
                # snapshot — log at debug and skip just that line
                logger.debug("proc_stat: skipping malformed line %r: %s", line, exc)
                continue
        return result


class ProcLoadAvgSource(MetricSource):
    """1/5/15 min load average and runnable/total task counts, from
    /proc/loadavg."""
    name = "proc_loadavg"

    def __init__(self, path: str = "/proc/loadavg") -> None:
        self._path = Path(path)

    def is_available(self) -> bool:
        return self._path.exists()

    def read(self) -> dict:
        try:
            parts = self._path.read_text().split()
        except OSError as exc:
            logger.warning("proc_loadavg: read failed: %s", exc)
            return {}
        try:
            runnable, total = parts[3].split("/")
            return {
                "load_avg_1": float(parts[0]),
                "load_avg_5": float(parts[1]),
                "load_avg_15": float(parts[2]),
                "runnable_procs": int(runnable),
                "total_procs": int(total),
            }
        except (IndexError, ValueError) as exc:
            logger.warning("proc_loadavg: parse failed: %s", exc)
            return {}


class ProcMemInfoSource(MetricSource):
    """Memory and swap utilization, from /proc/meminfo."""
    name = "proc_meminfo"

    def __init__(self, path: str = "/proc/meminfo") -> None:
        self._path = Path(path)

    def is_available(self) -> bool:
        return self._path.exists()

    def read(self) -> dict:
        try:
            text = self._path.read_text()
        except OSError as exc:
            logger.warning("proc_meminfo: read failed: %s", exc)
            return {}

        values: dict[str, int] = {}
        for line in text.splitlines():
            m = re.match(r"^(\w+):\s+(\d+)\s*kB", line)
            if m:
                values[m.group(1)] = int(m.group(2))

        total = values.get("MemTotal")
        available = values.get("MemAvailable")
        result: dict = {}
        if total is not None:
            result["mem_total_kb"] = total
        if available is not None:
            result["mem_available_kb"] = available
        if total and available is not None:
            result["mem_util_pct"] = 100.0 * (total - available) / total
        if "SwapTotal" in values:
            result["swap_total_kb"] = values["SwapTotal"]
        if "SwapFree" in values:
            result["swap_free_kb"] = values["SwapFree"]
        return result


class CpuFreqSource(MetricSource):
    """Current CPU frequency, averaged across cores, from
    /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq. Not present in
    many VMs/containers — capability-checked accordingly, and the Monitor
    is expected to run fine without it (see architecture doc, Section 3.1).
    """
    name = "cpu_freq"

    def __init__(
        self,
        glob_pattern: str = "/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq",
    ) -> None:
        self._glob_pattern = glob_pattern

    def is_available(self) -> bool:
        return len(glob.glob(self._glob_pattern)) > 0

    def read(self) -> dict:
        freqs = []
        for path in glob.glob(self._glob_pattern):
            try:
                freqs.append(int(Path(path).read_text().strip()))
            except (OSError, ValueError):
                continue
        if not freqs:
            return {}
        # scaling_cur_freq is in kHz
        return {"cpu_freq_mhz": sum(freqs) / len(freqs) / 1000.0}


class SysctlSchedSource(MetricSource):
    """Currently-effective scheduler tunables, read via sysctl. Only reads
    keys present in the given ParameterRegistry-like list of names, so this
    source has no hardcoded knowledge of which tunables matter — that lives
    in scheduler/registry.py (architecture doc, Section 9.3).
    """
    name = "sysctl_sched"

    def __init__(self, keys: tuple[str, ...] = ()) -> None:
        self._keys = keys
        self._available_keys: tuple[str, ...] = ()

    def is_available(self) -> bool:
        if not self._keys:
            return False
        available = []
        for key in self._keys:
            path = Path("/proc/sys/" + key.replace(".", "/"))
            if path.exists():
                available.append(key)
        self._available_keys = tuple(available)
        return len(self._available_keys) > 0

    def read(self) -> dict:
        if not self._available_keys:
            return {}
        result: dict[str, float] = {}
        for key in self._available_keys:
            path = Path("/proc/sys/" + key.replace(".", "/"))
            try:
                raw = path.read_text().strip()
                result[key] = float(raw)
            except (OSError, ValueError) as exc:
                logger.debug("sysctl_sched: could not read %s: %s", key, exc)
        return {"sched_params": result} if result else {}


class NumaSource(MetricSource):
    """NUMA topology presence, from /sys/devices/system/node. Many dev
    machines/containers report a single node or none at all — this source
    reports what's actually there rather than assuming a topology.
    """
    name = "numa"

    def __init__(self, base_path: str = "/sys/devices/system/node") -> None:
        self._base_path = Path(base_path)

    def is_available(self) -> bool:
        return self._base_path.exists()

    def read(self) -> dict:
        try:
            nodes = sorted(
                p.name for p in self._base_path.iterdir()
                if p.is_dir() and re.match(r"^node\d+$", p.name)
            )
        except OSError as exc:
            logger.warning("numa: read failed: %s", exc)
            return {}
        return {"numa_nodes": tuple(nodes)} if nodes else {}


class ProcessSampleSource(MetricSource):
    """Scan /proc counters and return up to `sample_size` busiest processes.

    The first sample and newly seen processes have zero interval ticks.
    Reading cost scales with process count; only the returned data is capped.
    """
    name = "process_sample"

    def __init__(self, sample_size: int = 25) -> None:
        self._sample_size = sample_size
        if sample_size < 1:
            raise ValueError("sample_size must be positive")
        self._previous_ticks = {}

    def is_available(self) -> bool:
        return Path("/proc").exists()

    def read(self) -> dict:
        procs = []
        try:
            pids = [p for p in os.listdir("/proc") if p.isdigit()]
        except OSError as exc:
            logger.warning("process_sample: listdir failed: %s", exc)
            return {}

        current_ticks = {}
        # Rank current activity before capping the returned sample. Taking the
        # first directory entries permanently hid newly busy processes.
        for pid in pids:
            stat_path = Path(f"/proc/{pid}/stat")
            try:
                raw = stat_path.read_text()
                # comm is whitespace-safe only because it's wrapped in ()
                comm_start = raw.index("(")
                comm_end = raw.rindex(")")
                comm = raw[comm_start + 1 : comm_end]
                rest = raw[comm_end + 2 :].split()
                state = rest[0]
                utime = int(rest[11])
                stime = int(rest[12])
                num_threads = int(rest[17])
                starttime = int(rest[19])
                identity = (int(pid), starttime)
                ticks = utime + stime
                delta = max(0, ticks - self._previous_ticks.get(identity, ticks))
                current_ticks[identity] = ticks
                procs.append(
                    {
                        "pid": int(pid),
                        "comm": comm,
                        "state": state,
                        "utime": utime,
                        "stime": stime,
                        "num_threads": num_threads,
                        "starttime": starttime,
                        "cpu_ticks_delta": delta,
                    }
                )
            except (OSError, ValueError, IndexError):
                # process exited between listdir and read, or malformed row —
                # both routine, not worth logging at anything above debug
                continue

        self._previous_ticks = current_ticks
        procs.sort(key=lambda row: (-row["cpu_ticks_delta"], row["pid"]))
        return {"processes": tuple(procs[:self._sample_size])} if procs else {}


class PerfStatSource(MetricSource):
    """Optional, expensive source: cache misses / IPC via `perf stat`.
    Deliberately NOT included in the default source list (see collector.py)
    since it forks a subprocess and often requires elevated perf_event
    permissions — sample this less frequently than the rest if you enable it.
    """
    name = "perf_stat"

    def __init__(self, duration_s: float = 0.2) -> None:
        self._duration_s = duration_s

    def is_available(self) -> bool:
        try:
            subprocess.run(
                ["perf", "--version"],
                capture_output=True,
                timeout=2,
                check=False,
            )
            return True
        except (OSError, subprocess.TimeoutExpired):
            return False

    def read(self) -> dict:
        try:
            proc = subprocess.run(
                [
                    "perf",
                    "stat",
                    "-e",
                    "cache-misses,instructions,cycles",
                    "sleep",
                    str(self._duration_s),
                ],
                capture_output=True,
                text=True,
                timeout=self._duration_s + 3,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("perf_stat: run failed: %s", exc)
            return {}

        result: dict = {}
        for line in proc.stderr.splitlines():
            line = line.strip().replace(",", "")
            m = re.match(r"^(\d+)\s+cache-misses", line)
            if m:
                result["cache_misses"] = int(m.group(1))
        return result
