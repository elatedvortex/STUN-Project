"""Unit tests for agents/self_tuner.py."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.self_tuner import SelfTunerAgent
from benchmarks.types import BenchmarkResult
from monitor.types import SystemSnapshot, ProcessInfo
from scheduler.registry import ParameterRegistry
from scheduler.types import ParameterMeta
from storage.db import StorageBackend


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_registry(params=None):
    r = ParameterRegistry()
    if params is None:
        params = [
            ParameterMeta(name="sched_rr_timeslice_ms",
                          path="kernel.sched_rr_timeslice_ms",
                          type=int, min_value=1, max_value=2000),
            ParameterMeta(name="sched_autogroup_enabled",
                          path="kernel.sched_autogroup_enabled",
                          type=int, min_value=0, max_value=1),
        ]
    for p in params:
        r.register(p)
    return r


def _snapshot(comms=(), sched_params=None):
    procs = tuple(
        ProcessInfo(pid=i + 1, comm=c, state="R", utime=100, stime=10, num_threads=1)
        for i, c in enumerate(comms)
    )
    if sched_params is None:
        sched_params = {
            "kernel.sched_rr_timeslice_ms": 100.0,
            "kernel.sched_autogroup_enabled": 1.0,
        }
    return SystemSnapshot(
        timestamp=datetime.now(timezone.utc),
        processes=procs,
        cpu_util_pct=30.0,
        load_avg_1=1.2,
        mem_util_pct=45.0,
        sched_params=sched_params,
    )


class _FakeMonitor:
    def __init__(self, comms=(), sched_params=None):
        self.comms = comms
        self.sched_params = sched_params

    def read_snapshot(self):
        return _snapshot(self.comms, self.sched_params)


class _FakeController:
    def __init__(self, raise_on_apply=False):
        self.applied: list[dict] = []
        self.rollbacks = 0
        self.raise_on_apply = raise_on_apply

    def apply_parameters(self, params):
        if self.raise_on_apply:
            raise RuntimeError("Simulated apply failure")
        self.applied.append(dict(params))

    def rollback(self):
        self.rollbacks += 1


def _make_bench_result(score=95.0, success=True):
    return BenchmarkResult(
        name="dry-run",
        workload_type="cpu",
        success=success,
        score=score,
        score_is_higher_better=True,
        metrics={"ops": score},
    )


# ── Tests: suggest_from_history ───────────────────────────────────────────────

def test_suggest_from_history_returns_none_when_empty():
    registry = _make_registry()
    storage = StorageBackend(":memory:")
    agent = SelfTunerAgent(
        monitor=_FakeMonitor(),
        controller=_FakeController(),
        storage=storage,
        registry=registry,
    )
    result = agent.suggest_from_history("compiler")  # process category, not workload type
    assert result is None


def test_suggest_from_history_returns_mapped_params():
    registry = _make_registry()
    storage = StorageBackend(":memory:")
    storage.write_benchmark_result(
        name="bench", workload_type="cpu", success=True, score=100.0,
        score_is_higher_better=True,
        metrics={"sched_params": {"kernel.sched_rr_timeslice_ms": 50}},
        tag="sweep:cpu",
    )
    agent = SelfTunerAgent(
        monitor=_FakeMonitor(),
        controller=_FakeController(),
        storage=storage,
        registry=registry,
    )
    # "compiler" is a process category that maps to workload_type "cpu"
    result = agent.suggest_from_history("compiler")
    assert result is not None
    assert "sched_rr_timeslice_ms" in result
    assert result["sched_rr_timeslice_ms"] == 50


def test_suggest_from_history_casts_to_correct_type():
    registry = _make_registry()
    storage = StorageBackend(":memory:")
    # Store as float (as DB returns)
    storage.write_benchmark_result(
        name="bench", workload_type="cpu", success=True, score=99.0,
        score_is_higher_better=True,
        metrics={"sched_params": {"kernel.sched_rr_timeslice_ms": 75.9}},
        tag="sweep:cpu",
    )
    agent = SelfTunerAgent(
        monitor=_FakeMonitor(),
        controller=_FakeController(),
        storage=storage,
        registry=registry,
    )
    # "compiler" maps to "cpu" benchmark type — finds the row above
    result = agent.suggest_from_history("compiler")
    assert result is not None
    assert isinstance(result["sched_rr_timeslice_ms"], int)


# ── Tests: heuristic_perturb ──────────────────────────────────────────────────

def test_heuristic_perturb_returns_registry_named_params():
    registry = _make_registry()
    agent = SelfTunerAgent(
        monitor=_FakeMonitor(),
        controller=_FakeController(),
        storage=StorageBackend(":memory:"),
        registry=registry,
    )
    snap = _snapshot(comms=["gcc"])  # compiler → cpu-heavy direction
    from workload.classifier import ProcessClassifier
    fp = ProcessClassifier().fingerprint(snap)
    result = agent.heuristic_perturb(snap, fp)
    # All returned keys must be registry logical names
    reg_names = {m.name for m in registry.get_all()}
    for k in result:
        assert k in reg_names, f"Unexpected key: {k}"


def test_heuristic_perturb_stays_within_bounds():
    registry = _make_registry()
    agent = SelfTunerAgent(
        monitor=_FakeMonitor(),
        controller=_FakeController(),
        storage=StorageBackend(":memory:"),
        registry=registry,
    )
    snap = _snapshot(comms=["bash"])
    from workload.classifier import ProcessClassifier
    fp = ProcessClassifier().fingerprint(snap)
    for _ in range(10):  # run multiple times to cover random variation
        result = agent.heuristic_perturb(snap, fp)
        for meta in registry.get_all():
            if meta.name in result:
                v = result[meta.name]
                assert float(meta.min_value) <= v <= float(meta.max_value), (
                    f"{meta.name}={v} out of [{meta.min_value}, {meta.max_value}]"
                )


def test_heuristic_perturb_empty_when_no_sched_params():
    """If snapshot.sched_params is empty, perturb returns empty dict."""
    registry = _make_registry()
    agent = SelfTunerAgent(
        monitor=_FakeMonitor(sched_params={}),
        controller=_FakeController(),
        storage=StorageBackend(":memory:"),
        registry=registry,
    )
    snap = _snapshot(comms=["bash"], sched_params={})
    from workload.classifier import ProcessClassifier
    fp = ProcessClassifier().fingerprint(snap)
    result = agent.heuristic_perturb(snap, fp)
    assert result == {}


# ── Tests: run_tuning_iteration ───────────────────────────────────────────────

def test_run_tuning_iteration_applies_history_params():
    registry = _make_registry()
    storage = StorageBackend(":memory:")
    storage.write_benchmark_result(
        name="bench", workload_type="cpu", success=True, score=100.0,
        score_is_higher_better=True,
        metrics={"sched_params": {"kernel.sched_rr_timeslice_ms": 42}},
        tag="sweep:cpu",
    )
    ctrl = _FakeController()
    agent = SelfTunerAgent(
        monitor=_FakeMonitor(comms=["gcc"]),
        controller=ctrl,
        storage=storage,
        registry=registry,
    )
    result = agent.run_tuning_iteration(run_benchmark=False)
    assert len(ctrl.applied) == 1
    assert ctrl.applied[0].get("sched_rr_timeslice_ms") == 42
    assert result["proposal"]["sched_rr_timeslice_ms"] == 42


def test_run_tuning_iteration_uses_heuristic_when_no_history():
    registry = _make_registry()
    ctrl = _FakeController()
    agent = SelfTunerAgent(
        monitor=_FakeMonitor(comms=["bash"]),
        controller=ctrl,
        storage=StorageBackend(":memory:"),
        registry=registry,
    )
    result = agent.run_tuning_iteration(run_benchmark=False)
    # heuristic_perturb was used; proposal may be empty if sched_params unavailable
    assert "proposal" in result


def test_run_tuning_iteration_with_benchmark():
    registry = _make_registry()
    ctrl = _FakeController()
    storage = StorageBackend(":memory:")

    bench_result = _make_bench_result(score=88.5)
    bench_mock = MagicMock()
    bench_mock.run.return_value = bench_result

    def bench_factory(workload_type):
        return bench_mock

    storage.write_benchmark_result(
        name="bench", workload_type="cpu", success=True, score=100.0,
        score_is_higher_better=True,
        metrics={"sched_params": {"kernel.sched_rr_timeslice_ms": 50}},
        tag="sweep:cpu",
    )

    agent = SelfTunerAgent(
        monitor=_FakeMonitor(comms=["gcc"]),
        controller=ctrl,
        storage=storage,
        registry=registry,
        benchmark_factory=bench_factory,
    )
    result = agent.run_tuning_iteration(run_benchmark=True)
    assert result["benchmark"] is bench_result
    assert bench_mock.run.call_count == 1


def test_run_tuning_iteration_apply_failure_does_not_undo_previous_transaction():
    registry = _make_registry()
    ctrl = _FakeController(raise_on_apply=True)
    storage = StorageBackend(":memory:")
    storage.write_benchmark_result(
        name="bench", workload_type="cpu", success=True, score=100.0,
        score_is_higher_better=True,
        metrics={"sched_params": {"kernel.sched_rr_timeslice_ms": 77}},
        tag="sweep:cpu",
    )
    agent = SelfTunerAgent(
        monitor=_FakeMonitor(comms=["gcc"]),
        controller=ctrl,
        storage=storage,
        registry=registry,
    )
    result = agent.run_tuning_iteration(run_benchmark=False)
    assert result["benchmark"] is None
    assert ctrl.rollbacks == 0


def test_run_tuning_iteration_benchmark_factory_none_skips_bench():
    registry = _make_registry()
    ctrl = _FakeController()
    storage = StorageBackend(":memory:")
    storage.write_benchmark_result(
        name="bench", workload_type="cpu", success=True, score=100.0,
        score_is_higher_better=True,
        metrics={"sched_params": {"kernel.sched_rr_timeslice_ms": 50}},
        tag="sweep:cpu",
    )
    agent = SelfTunerAgent(
        monitor=_FakeMonitor(comms=["gcc"]),
        controller=ctrl,
        storage=storage,
        registry=registry,
        benchmark_factory=None,
    )
    result = agent.run_tuning_iteration(run_benchmark=True)
    assert result["benchmark"] is None  # no factory → no benchmark


# ── Tests: _convert_sched_params_to_registry_names ───────────────────────────

def test_convert_sched_params_maps_paths_to_names():
    registry = _make_registry()
    agent = SelfTunerAgent(
        monitor=_FakeMonitor(),
        controller=_FakeController(),
        storage=StorageBackend(":memory:"),
        registry=registry,
    )
    out = agent._convert_sched_params_to_registry_names({
        "kernel.sched_rr_timeslice_ms": 100,
        "kernel.sched_autogroup_enabled": 1,
        "kernel.unknown_param": 999,  # not in registry — should be skipped
    })
    assert "sched_rr_timeslice_ms" in out
    assert "sched_autogroup_enabled" in out
    assert "unknown_param" not in out
    assert out["sched_rr_timeslice_ms"] == 100


def test_convert_sched_params_skips_bad_cast():
    registry = _make_registry()
    agent = SelfTunerAgent(
        monitor=_FakeMonitor(),
        controller=_FakeController(),
        storage=StorageBackend(":memory:"),
        registry=registry,
    )
    # "not_a_number" cannot be cast to int — should be silently skipped
    out = agent._convert_sched_params_to_registry_names({
        "kernel.sched_rr_timeslice_ms": "not_a_number",
    })
    assert "sched_rr_timeslice_ms" not in out
