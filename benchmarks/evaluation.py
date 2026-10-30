"""Repeated paired comparisons using raw benchmark scores, not shaped rewards."""
from __future__ import annotations

import math
import random
import statistics
from dataclasses import asdict
from datetime import datetime, timezone


def compare_configs(controller, benchmark, candidates, *, repeats=10, seed=42,
                    benchmark_kwargs=None, on_record=None):
    """Randomise method order within each repeat and restore between trials.

    The caller owns the persistent recovery checkpoint/watchdog lifecycle.
    Candidates must be chosen on separate training data. Results describe this
    machine and benchmark only; they do not establish general workload gains.
    """
    if repeats < 2:
        raise ValueError("At least two repeats are required")
    if not candidates or "baseline" in candidates:
        raise ValueError("Provide candidates without the reserved name 'baseline'")
    baseline = controller.read_state()
    methods = {"baseline": {}, **candidates}
    rng = random.Random(seed)
    records = []
    try:
        for repeat in range(repeats):
            order = list(methods)
            rng.shuffle(order)
            for method in order:
                controller.restore_state(baseline)
                if methods[method]:
                    controller.apply_parameters(methods[method])
                result = benchmark.run(**(benchmark_kwargs or {}))
                if result.success and not math.isfinite(result.score):
                    raise ValueError("Benchmark returned a non-finite score")
                record = {
                    "repeat": repeat, "method": method,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "params": controller.read_state(), "result": asdict(result),
                }
                records.append(record)
                if on_record:
                    on_record(record)
    finally:
        controller.restore_state(baseline)

    return {"seed": seed, "repeats": repeats, "baseline_params": baseline,
            "records": records, "summary": summarize_records(records, seed=seed)}


def summarize_records(records, *, seed=42, bootstrap_samples=2000):
    """Pair independent repeats, with a percentile bootstrap interval on the mean.

    Steps within an episode are not independent repeats. Failure counts remain
    visible, and intervals are omitted when fewer than three valid pairs exist.
    """
    methods = list(dict.fromkeys(row["method"] for row in records))
    repeats = sorted({row["repeat"] for row in records})
    summary = {}
    for method in methods:
        successful = [r["result"]["score"] for r in records
                      if r["method"] == method and r["result"]["success"]]
        paired = []
        for repeat in repeats:
            pair = {r["method"]: r["result"] for r in records if r["repeat"] == repeat}
            base, candidate = pair["baseline"], pair[method]
            if not base["success"] or not candidate["success"] or base["score"] <= 0:
                continue
            if (base["name"], base["score_is_higher_better"]) != (
                    candidate["name"], candidate["score_is_higher_better"]):
                raise ValueError("Cannot compare different benchmarks or score directions")
            direction = 1 if base["score_is_higher_better"] else -1
            paired.append(direction * (candidate["score"] - base["score"]) / base["score"] * 100)
        summary[method] = {
            "successful_runs": len(successful), "total_runs": len(repeats),
            "mean_score": statistics.mean(successful) if successful else None,
            "std_score": statistics.stdev(successful) if len(successful) > 1 else None,
            "paired_runs": len(paired),
            "mean_improvement_pct": statistics.mean(paired) if paired else None,
            "std_improvement_pct": statistics.stdev(paired) if len(paired) > 1 else None,
            "mean_improvement_ci95_pct": _bootstrap_mean(paired, seed, bootstrap_samples),
        }
    return summary


def _bootstrap_mean(values, seed, samples):
    if len(values) < 3:
        return None
    rng = random.Random(seed)
    means = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(samples))
    return [means[int(samples * 0.025)], means[min(samples - 1, int(samples * 0.975))]]


def compare_policies(env, policies, *, configs=None, repeats=10, steps=5, seed=42, on_record=None):
    """Compare adaptive policies, random actions and baseline with equal step budgets.

    Policy callables map observations to actions. All methods start each repeat
    at the same captured baseline; rewards are never used as performance scores.
    The env must benchmark every step. No model updates happen here.
    """
    if repeats < 2 or steps < 1 or steps > env._episode_steps:
        raise ValueError("Require repeats >= 2 and 1 <= steps <= episode_steps")
    configs = configs or {}
    if set(policies) & set(configs):
        raise ValueError("Policy and fixed configuration names must be distinct")
    if {"baseline", "random"} & (set(policies) | set(configs)) or not policies:
        raise ValueError("Provide policies without the reserved names baseline/random")
    if env._benchmark_interval != 1:
        raise ValueError("Policy evaluation must benchmark every step")
    methods = ["baseline", "random", *policies, *configs]
    order_rng = random.Random(seed)
    records = []
    try:
        for repeat in range(repeats):
            order = list(methods)
            order_rng.shuffle(order)
            for method in order:
                env._reward_shaper.reset()
                obs, _ = env.reset(seed=seed + repeat)
                env.action_space.seed(seed + repeat)
                if method in configs:
                    env._controller.apply_parameters(configs[method])
                trajectory = []
                for step in range(steps):
                    if method == "baseline" or method in configs:
                        obs, _, _, _, info = env.measure_baseline()
                        action = None
                    else:
                        action = (env.action_space.sample() if method == "random"
                                  else policies[method](obs))
                        obs, _, _, _, info = env.step(action)
                    result = info["benchmark"]
                    if result.success and not math.isfinite(result.score):
                        raise ValueError("Benchmark returned a non-finite score")
                    trajectory.append({
                        "step": step, "action": action.tolist() if hasattr(action, "tolist") else action,
                        "params_applied": info["params_applied"],
                        "action_rejected": info["rollback_triggered"], "result": asdict(result),
                        "params_readback": env._controller.read_state(),
                    })
                results = [row["result"] for row in trajectory]
                if len({(r["name"], r["score_is_higher_better"]) for r in results}) != 1:
                    raise ValueError("Benchmark changed within a trajectory")
                combined = dict(results[0])
                combined.update({
                    "success": all(r["success"] for r in results),
                    "score": statistics.mean(r["score"] for r in results),
                    "metrics": {"steps": steps}, "raw_output": "See trajectory", 
                })
                record = {
                    "repeat": repeat, "method": method, "result": combined,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "trajectory": trajectory,
                    "fixed_config": configs.get(method),
                    "rejected_actions": sum(row["action_rejected"] for row in trajectory),
                }
                records.append(record)
                if on_record:
                    on_record(record)
    finally:
        env.close()
    return {"seed": seed, "repeats": repeats, "steps_per_repeat": steps,
            "baseline_params": env._baseline,
            "records": records, "summary": summarize_records(records, seed=seed),
            "scope": "Adaptive inference trajectories; scores averaged per independent repeat"}
