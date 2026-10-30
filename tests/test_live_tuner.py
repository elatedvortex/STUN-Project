"""Unit tests for agents/live_tuner.py."""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.live_tuner import LiveTunerAgent
from monitor.types import SystemSnapshot, ProcessInfo
from scheduler.registry import ParameterRegistry
from scheduler.types import ParameterMeta
from storage.db import StorageBackend


def _snapshot(comms=()):
    procs = tuple(
        ProcessInfo(pid=i+1, comm=comm, state="R", utime=100, stime=10, num_threads=1)
        for i, comm in enumerate(comms)
    )
    return SystemSnapshot(
        timestamp=datetime.now(timezone.utc),
        processes=procs,
        cpu_util_pct=20.0,
        load_avg_1=1.0,
        mem_util_pct=40.0,
    )


class _FakeMonitor:
    def __init__(self, comms=()):
        self.comms = comms
    def read_snapshot(self):
        return _snapshot(self.comms)


class _FakeController:
    def __init__(self):
        self.applied = []
        self.rollbacks = 0
    def apply_parameters(self, params):
        self.applied.append(dict(params))
    def rollback(self):
        self.rollbacks += 1


def _make_registry():
    r = ParameterRegistry()
    r.register(ParameterMeta(
        name="sched_rr_timeslice_ms",
        path="kernel.sched_rr_timeslice_ms",
        type=int, min_value=1, max_value=2000,
    ))
    return r


def _seed_storage(storage, workload_type, sched_params, score=100.0):
    metrics = {"sched_params": sched_params}
    storage.write_benchmark_result(
        name="fake-bench",
        workload_type=workload_type,
        success=True,
        score=score,
        score_is_higher_better=True,
        metrics=metrics,
        tag=f"sweep:{workload_type}",
    )


def test_live_tuner_applies_params_on_category_change():
    registry = _make_registry()
    storage = StorageBackend(":memory:")
    _seed_storage(storage, "cpu", {"kernel.sched_rr_timeslice_ms": 50})

    monitor = _FakeMonitor(comms=["gcc"])
    ctrl = _FakeController()

    agent = LiveTunerAgent(
        monitor=monitor, controller=ctrl, storage=storage,
        registry=registry, dry_run=True,
    )
    status = agent.run_once()

    assert status["workload_type"] == "cpu"
    assert status["applied"] is True
    assert status["best_found"] is True


def test_live_tuner_hysteresis():
    registry = _make_registry()
    storage = StorageBackend(":memory:")
    _seed_storage(storage, "cpu", {"kernel.sched_rr_timeslice_ms": 50})

    monitor = _FakeMonitor(comms=["gcc"])
    ctrl = _FakeController()

    agent = LiveTunerAgent(
        monitor=monitor, controller=ctrl, storage=storage,
        registry=registry, dry_run=True,
    )
    agent.run_once()
    status = agent.run_once()

    assert status["skipped_reason"] == "hysteresis"


def test_live_tuner_no_sweep_data():
    registry = _make_registry()
    storage = StorageBackend(":memory:")

    monitor = _FakeMonitor(comms=["chrome"])
    ctrl = _FakeController()

    agent = LiveTunerAgent(
        monitor=monitor, controller=ctrl, storage=storage,
        registry=registry, dry_run=True,
    )
    status = agent.run_once()

    assert status["applied"] is False
    assert status["skipped_reason"] == "no_sweep_data"


def test_live_tuner_applies_on_category_switch():
    registry = _make_registry()
    storage = StorageBackend(":memory:")
    _seed_storage(storage, "interactive", {"kernel.sched_rr_timeslice_ms": 20})
    _seed_storage(storage, "gaming",      {"kernel.sched_rr_timeslice_ms": 5})

    ctrl = _FakeController()

    monitor = _FakeMonitor(comms=["chrome"])
    agent = LiveTunerAgent(
        monitor=monitor, controller=ctrl, storage=storage,
        registry=registry, dry_run=True,
    )
    s1 = agent.run_once()
    assert s1["applied"] is True

    agent.monitor = _FakeMonitor(comms=["wine"])
    s2 = agent.run_once()
    assert s2["applied"] is True
    assert s2["workload_type"] == "gaming"


def test_live_tuner_cache_invalidate():
    registry = _make_registry()
    storage = StorageBackend(":memory:")
    _seed_storage(storage, "cpu", {"kernel.sched_rr_timeslice_ms": 50}, score=100.0)

    monitor = _FakeMonitor(comms=["gcc"])
    ctrl = _FakeController()

    agent = LiveTunerAgent(
        monitor=monitor, controller=ctrl, storage=storage,
        registry=registry, dry_run=True, cache_ttl=9999.0,
    )
    agent.run_once()
    assert len(agent._cache) > 0
    agent.invalidate_cache()
    assert len(agent._cache) == 0


def test_live_tuner_skips_idle_and_unrecognised_activity():
    from dataclasses import replace
    registry = _make_registry()
    storage = StorageBackend(":memory:")
    _seed_storage(storage, "cpu", {"kernel.sched_rr_timeslice_ms": 50})
    snapshot = _snapshot(["gcc", "unknown-compute-task"])
    controller = _FakeController()

    class Monitor:
        def read_snapshot(self):
            return replace(snapshot, processes=tuple(
                replace(proc, cpu_ticks_delta=ticks)
                for proc, ticks in zip(snapshot.processes, [1, 99])))

    agent = LiveTunerAgent(Monitor(), controller, storage, registry)
    result = agent.run_once()
    assert result["skipped_reason"] == "insufficient_workload_evidence"
    assert not controller.applied
