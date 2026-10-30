import pytest

from benchmarks.evaluation import compare_configs
from benchmarks.evaluation import compare_policies, _bootstrap_mean
from benchmarks.types import BenchmarkResult
from tests.test_recovery import system


@pytest.mark.parametrize("higher,expected", [(True, 100.0), (False, -100.0)])
def test_comparison_pairs_raw_scores_and_restores(system, higher, expected):
    controller, _ = system

    class Benchmark:
        def run(self, **kwargs):
            return BenchmarkResult("fake", "cpu", True, controller.read_state()["a"], higher)

    records = []
    report = compare_configs(controller, Benchmark(), {"candidate": {"a": 20}},
                             repeats=4, seed=12, on_record=records.append)
    assert len(records) == 8
    assert report["summary"]["candidate"]["mean_improvement_pct"] == expected
    assert report["summary"]["candidate"]["paired_runs"] == 4
    assert report["summary"]["candidate"]["std_score"] == 0
    assert controller.read_state() == {"a": 10, "b": 20}
    assert {r["method"] for r in records[:2]} == {"baseline", "candidate"}


def test_comparison_restores_when_benchmark_raises(system):
    controller, _ = system

    class Benchmark:
        def run(self, **kwargs):
            raise RuntimeError("benchmark crashed")

    with pytest.raises(RuntimeError, match="benchmark crashed"):
        compare_configs(controller, Benchmark(), {"candidate": {"a": 20}}, seed=1)
    assert controller.read_state() == {"a": 10, "b": 20}


def test_failed_benchmarks_do_not_count_as_improvements(system):
    controller, _ = system

    class Benchmark:
        def run(self, **kwargs):
            return BenchmarkResult("fake", "cpu", False, 0, True)

    report = compare_configs(controller, Benchmark(), {"candidate": {"a": 20}})
    assert report["summary"]["candidate"]["paired_runs"] == 0
    assert report["summary"]["candidate"]["mean_improvement_pct"] is None


def test_policy_comparison_uses_raw_trajectory_scores_and_equal_budgets():
    from tests.test_rl_env import _make_env
    env, backend = _make_env(episode_steps=3)
    original = dict(backend.state)
    calls = []

    def benchmark(**kwargs):
        return BenchmarkResult("fake", "cpu", True,
                               float(backend.state["kernel.sched_min_granularity_ns"]), True)

    def policy(obs):
        calls.append(obs.copy())
        return 1

    env._benchmark.run = benchmark
    report = compare_policies(env, {"policy": policy}, repeats=3, steps=2)
    assert len(calls) == 6
    assert len(report["records"]) == 9
    assert all(len(row["trajectory"]) == 2 for row in report["records"])
    assert report["summary"]["baseline"]["mean_score"] == 3_000_000
    assert report["summary"]["policy"]["mean_score"] == 10_492_500
    assert report["summary"]["policy"]["paired_runs"] == 3
    assert backend.state == original


def test_continuous_baseline_measures_without_midpoint_writes():
    import numpy as np
    from tests.test_rl_env import _make_env
    env, backend = _make_env(episode_steps=2, action_mode="continuous")
    env._benchmark.run = lambda **kwargs: BenchmarkResult(
        "fake", "cpu", True, float(backend.state["kernel.sched_min_granularity_ns"]), True)
    report = compare_policies(env, {"policy": lambda obs: np.zeros(2)}, repeats=2, steps=1,
                              configs={"fixed": {"sched_min_granularity_ns": 5_000_000}})
    assert report["summary"]["baseline"]["mean_score"] == 3_000_000
    assert report["summary"]["fixed"]["mean_score"] == 5_000_000
    assert report["summary"]["policy"]["mean_score"] == 50_050_000


def test_policy_failure_restores_baseline():
    from tests.test_rl_env import _make_env
    env, backend = _make_env(episode_steps=2)
    original = dict(backend.state)

    def fail(obs):
        raise RuntimeError("bad model")

    with pytest.raises(RuntimeError, match="bad model"):
        compare_policies(env, {"policy": fail}, repeats=2, steps=2)
    assert backend.state == original


def test_bootstrap_is_reproducible_and_omits_insufficient_pairs():
    assert _bootstrap_mean([10, 10], 42, 500) is None
    assert _bootstrap_mean([10, 10, 10], 42, 500) == [10, 10]
    assert _bootstrap_mean([1, 10, 20, -5], 42, 500) == _bootstrap_mean([1, 10, 20, -5], 42, 500)
