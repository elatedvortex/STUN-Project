"""
Unit tests for monitor/. Deliberately do not touch the real /proc or /sys —
sources are given fake paths pointing at tmp_path fixtures, so this suite
runs in ordinary CI with no root and no assumptions about the host kernel
(architecture doc, Section 6: "keep root-requiring tests behind a marker").
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from monitor.collector import Monitor
from monitor.sources import (
    CpuFreqSource,
    ProcLoadAvgSource,
    ProcMemInfoSource,
    ProcStatSource,
)
from monitor.types import SystemSnapshot


# ---------- ProcStatSource ----------

def test_proc_stat_first_read_has_no_util_delta(tmp_path: Path) -> None:
    stat_file = tmp_path / "stat"
    stat_file.write_text("cpu  100 0 100 800 0 0 0 0 0 0\nctxt 5000\nprocs_running 2\n")
    source = ProcStatSource(path=str(stat_file))
    assert source.is_available()
    result = source.read()
    # first read: no previous sample, so no util pct yet
    assert "cpu_util_pct" not in result
    assert result["ctxt_switches_total"] == 5000
    assert result["runnable_procs"] == 2


def test_proc_stat_second_read_computes_delta(tmp_path: Path) -> None:
    stat_file = tmp_path / "stat"
    stat_file.write_text("cpu  100 0 100 800 0 0 0 0 0 0\nctxt 5000\nprocs_running 2\n")
    source = ProcStatSource(path=str(stat_file))
    source.read()  # establish baseline

    # advance: +100 busy ticks, +100 idle ticks -> 50% util this interval
    stat_file.write_text("cpu  150 0 150 900 0 0 0 0 0 0\nctxt 5200\nprocs_running 1\n")
    result = source.read()
    assert result["cpu_util_pct"] == pytest.approx(50.0, abs=0.5)
    assert result["ctxt_switches_delta"] == 200


def test_proc_stat_missing_file_is_unavailable(tmp_path: Path) -> None:
    source = ProcStatSource(path=str(tmp_path / "does_not_exist"))
    assert not source.is_available()


def test_proc_stat_malformed_line_does_not_raise(tmp_path: Path) -> None:
    stat_file = tmp_path / "stat"
    stat_file.write_text("cpu  not numbers here\nctxt 5000\n")
    source = ProcStatSource(path=str(stat_file))
    result = source.read()
    # malformed cpu line must be skipped (not raise), but a valid line
    # elsewhere in the same file should still parse — per-line resilience,
    # not all-or-nothing
    assert "cpu_util_pct" not in result
    assert result["ctxt_switches_total"] == 5000


# ---------- ProcLoadAvgSource ----------

def test_proc_loadavg_parses_all_fields(tmp_path: Path) -> None:
    f = tmp_path / "loadavg"
    f.write_text("0.52 0.58 0.59 3/512 12345\n")
    source = ProcLoadAvgSource(path=str(f))
    result = source.read()
    assert result == {
        "load_avg_1": 0.52,
        "load_avg_5": 0.58,
        "load_avg_15": 0.59,
        "runnable_procs": 3,
        "total_procs": 512,
    }


def test_proc_loadavg_malformed_degrades_to_empty(tmp_path: Path) -> None:
    f = tmp_path / "loadavg"
    f.write_text("garbage\n")
    source = ProcLoadAvgSource(path=str(f))
    assert source.read() == {}


# ---------- ProcMemInfoSource ----------

def test_proc_meminfo_computes_util_pct(tmp_path: Path) -> None:
    f = tmp_path / "meminfo"
    f.write_text(
        "MemTotal:        1000000 kB\n"
        "MemFree:          200000 kB\n"
        "MemAvailable:     400000 kB\n"
        "SwapTotal:        500000 kB\n"
        "SwapFree:         500000 kB\n"
    )
    source = ProcMemInfoSource(path=str(f))
    result = source.read()
    assert result["mem_total_kb"] == 1_000_000
    assert result["mem_available_kb"] == 400_000
    assert result["mem_util_pct"] == pytest.approx(60.0)
    assert result["swap_total_kb"] == 500_000
    assert result["swap_free_kb"] == 500_000


# ---------- CpuFreqSource ----------

def test_cpu_freq_averages_across_cores(tmp_path: Path) -> None:
    for core in (0, 1):
        core_dir = tmp_path / f"cpu{core}" / "cpufreq"
        core_dir.mkdir(parents=True)
        (core_dir / "scaling_cur_freq").write_text(str(2_000_000 + core * 1_000_000))
    source = CpuFreqSource(glob_pattern=str(tmp_path / "cpu[0-9]*/cpufreq/scaling_cur_freq"))
    assert source.is_available()
    result = source.read()
    # (2000000 + 3000000) / 2 kHz -> 2500 MHz
    assert result["cpu_freq_mhz"] == pytest.approx(2500.0)


def test_cpu_freq_unavailable_when_no_matches(tmp_path: Path) -> None:
    source = CpuFreqSource(glob_pattern=str(tmp_path / "nonexistent/*/scaling_cur_freq"))
    assert not source.is_available()


# ---------- Monitor / Collector integration (with fakes, not real sources) ----------

class _FakeSource:
    def __init__(self, name: str, available: bool, data: dict) -> None:
        self.name = name
        self._available = available
        self._data = data

    def is_available(self) -> bool:
        return self._available

    def read(self) -> dict:
        return self._data


class _RaisingSource:
    """Simulates a source whose read() throws — Collector must not propagate."""
    name = "raising_source"

    def is_available(self) -> bool:
        return True

    def read(self) -> dict:
        raise RuntimeError("simulated failure")


def test_monitor_skips_unavailable_sources() -> None:
    sources = [
        _FakeSource("available_one", True, {"cpu_util_pct": 42.0}),
        _FakeSource("unavailable_one", False, {"cpu_util_pct": 999.0}),
    ]
    monitor = Monitor(sources=sources)
    caps = monitor.check_capabilities()
    assert caps == {"available_one": True, "unavailable_one": False}

    snapshot = monitor.read_snapshot()
    assert snapshot.cpu_util_pct == 42.0
    assert snapshot.available_sources == ("available_one",)


def test_monitor_survives_a_raising_source() -> None:
    sources = [
        _FakeSource("good_source", True, {"cpu_util_pct": 10.0}),
        _RaisingSource(),
    ]
    monitor = Monitor(sources=sources)
    monitor.check_capabilities()
    # must not raise, and must still return data from the good source
    snapshot = monitor.read_snapshot()
    assert snapshot.cpu_util_pct == 10.0
    assert "raising_source" not in snapshot.available_sources


def test_snapshot_fields_default_to_none_when_no_sources() -> None:
    monitor = Monitor(sources=[])
    monitor.check_capabilities()
    snapshot = monitor.read_snapshot()
    assert snapshot.cpu_util_pct is None
    assert snapshot.mem_util_pct is None
    assert snapshot.available_sources == ()
    assert isinstance(snapshot, SystemSnapshot)


def test_process_sampling_ranks_interval_activity_and_handles_pid_reuse(monkeypatch):
    from monitor.sources import ProcessSampleSource
    frames = {"1": (1000, 10), "2": (10, 20)}

    def read_stat(path):
        pid = str(path).split("/")[2]
        ticks, start = frames[pid]
        fields = ["0"] * 20
        fields[0], fields[11], fields[17], fields[19] = "R", str(ticks), "1", str(start)
        return f"{pid} (worker) " + " ".join(fields)

    monkeypatch.setattr("monitor.sources.os.listdir", lambda path: ["1", "2"])
    monkeypatch.setattr(Path, "read_text", read_stat)
    source = ProcessSampleSource(sample_size=1)
    assert source.read()["processes"][0]["cpu_ticks_delta"] == 0
    frames["2"] = (40, 20)
    result = source.read()["processes"][0]
    assert result["pid"] == 2
    assert result["cpu_ticks_delta"] == 30
    frames["2"] = (50, 999)  # same PID, different process
    assert all(row["cpu_ticks_delta"] == 0 for row in source.read()["processes"])
