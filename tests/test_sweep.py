"""Unit tests for benchmarks/sweep.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.sweep import ParameterSweep, SweepSummary, _linspace, _candidate_values
from benchmarks.types import BenchmarkResult
from scheduler.registry import ParameterRegistry
from scheduler.types import ParameterMeta
from storage.db import StorageBackend


def _make_registry(*params):
    r = ParameterRegistry()
    for p in params:
        r.register(p)
    return r


def _meta(name, lo, hi, typ=int):
    return ParameterMeta(name=name, path=f"kernel.{name}", type=typ, min_value=lo, max_value=hi)


class _FakeController:
    def __init__(self):
        self.applied = []
        self.rolled_back = 0

    def apply_parameters(self, params):
        self.applied.append(dict(params))

    def rollback(self):
        self.rolled_back += 1


class _FakeBench:
    def __init__(self, score_fn=None):
        self.name = "fake"
        self.workload_type = "cpu"
        self._score_fn = score_fn or (lambda **_: 42.0)

    def run(self, **kwargs):
        score = self._score_fn(**kwargs)
        return BenchmarkResult(
            name=self.name, workload_type=self.workload_type,
            success=True, score=score, score_is_higher_better=True,
            metrics={"score": score},
        )


def test_linspace_two_steps():
    result = _linspace(0.0, 10.0, 2)
    assert result == [0.0, 10.0]


def test_linspace_five_steps():
    result = _linspace(0.0, 4.0, 5)
    assert result == [0.0, 1.0, 2.0, 3.0, 4.0]


def test_linspace_one_step():
    result = _linspace(0.0, 10.0, 1)
    assert result == [5.0]


def test_sweep_coordinate_dry_run_runs():
    reg = _make_registry(
        _meta("param_a", 1, 10),
        _meta("param_b", 100, 500),
    )
    storage = StorageBackend(":memory:")
    ctrl = _FakeController()
    sweep = ParameterSweep(
        registry=reg,
        controller=ctrl,
        storage=storage,
        benchmark_factory=lambda wt: _FakeBench(),
        steps_per_param=3,
        strategy="coordinate",
        dry_run=True,
    )
    summary = sweep.run("cpu")

    assert summary.workload_type == "cpu"
    assert summary.total_runs == 6
    assert summary.successful_runs == 6
    assert ctrl.applied == []
    assert ctrl.rolled_back == 0


def test_sweep_coordinate_finds_best_param():
    reg = _make_registry(_meta("latency", 1, 5))
    storage = StorageBackend(":memory:")
    ctrl = _FakeController()

    scores = iter([10.0, 20.0, 30.0, 50.0, 15.0])
    bench = _FakeBench(score_fn=lambda **_: next(scores))

    sweep = ParameterSweep(
        registry=reg, controller=ctrl, storage=storage,
        benchmark_factory=lambda wt: bench,
        steps_per_param=5, strategy="coordinate", dry_run=True,
    )
    summary = sweep.run("cpu")
    assert summary.best_score == 50.0
    assert summary.total_runs == 5


def test_sweep_estimate_run_count():
    reg = _make_registry(_meta("p1", 0, 1), _meta("p2", 0, 1), _meta("p3", 0, 1))
    storage = StorageBackend(":memory:")
    ctrl = _FakeController()
    sweep = ParameterSweep(
        registry=reg, controller=ctrl, storage=storage,
        benchmark_factory=lambda wt: _FakeBench(),
        steps_per_param=4,
    )
    est = sweep.estimate_run_count()
    assert est["coordinate"] == 12
    assert est["cartesian"] == 64


def test_sweep_results_persisted_to_db():
    reg = _make_registry(_meta("param_x", 1, 10))
    storage = StorageBackend(":memory:")
    ctrl = _FakeController()
    sweep = ParameterSweep(
        registry=reg, controller=ctrl, storage=storage,
        benchmark_factory=lambda wt: _FakeBench(),
        steps_per_param=3, dry_run=True,
    )
    sweep.run("cpu")
    assert storage.count_benchmark_results() == 3


def test_best_params_for_workload_after_sweep():
    reg = _make_registry(_meta("param_x", 1, 10))
    storage = StorageBackend(":memory:")
    ctrl = _FakeController()
    scores = iter([10.0, 99.0, 5.0])
    bench = _FakeBench(score_fn=lambda **_: next(scores))
    sweep = ParameterSweep(
        registry=reg, controller=ctrl, storage=storage,
        benchmark_factory=lambda wt: bench,
        steps_per_param=3, dry_run=True,
    )
    sweep.run("cpu")
    best = storage.best_params_for_workload("cpu", tag_prefix="dry-run-sweep")
    assert best is not None
    assert best["score"] == 99.0
    assert "sched_params" in best
    assert storage.best_params_for_workload("cpu") is None


def test_legacy_sweep_rows_marked_dry_run_are_excluded():
    storage = StorageBackend(":memory:")
    storage.write_benchmark_result(
        name="fake", workload_type="cpu", success=True, score=99,
        score_is_higher_better=True, tag="sweep:cpu",
        metrics={"dry_run": True, "sched_params": {"kernel.x": 1}},
    )
    assert storage.best_params_for_workload("cpu") is None


def test_cartesian_sweep_dry_run():
    reg = _make_registry(
        _meta("p1", 0, 2),
        _meta("p2", 0, 2),
    )
    storage = StorageBackend(":memory:")
    ctrl = _FakeController()
    sweep = ParameterSweep(
        registry=reg, controller=ctrl, storage=storage,
        benchmark_factory=lambda wt: _FakeBench(),
        steps_per_param=3, strategy="cartesian", dry_run=True,
    )
    summary = sweep.run("cpu")
    assert summary.total_runs == 9
    assert summary.successful_runs == 9


def test_library_sweep_holds_lease_and_restores_on_interruption(tmp_path):
    from scheduler import SchedulerController, Validator, Writer, RollbackStack, ProfileStore
    from safety.lease import HostLease
    reg = _make_registry(_meta("a", 1, 100))

    class Backend:
        value = 10
        def read(self, path):
            return str(self.value)
        def write(self, path, value):
            self.value = value

    backend = Backend()
    controller = SchedulerController(reg, Validator(reg), Writer(reg, backend),
                                     RollbackStack(), ProfileStore())
    controller._host_lease = HostLease(tmp_path / "lease")

    class InterruptedBenchmark:
        def run(self, **kwargs):
            with pytest.raises(RuntimeError, match="Another scheduler"):
                with HostLease(tmp_path / "lease").hold():
                    pytest.fail("another process must not enter during the benchmark")
            raise KeyboardInterrupt()

    sweep = ParameterSweep(reg, controller, StorageBackend(":memory:"),
                           lambda workload: InterruptedBenchmark())
    with pytest.raises(KeyboardInterrupt):
        sweep.run("cpu")
    assert backend.value == 10
