#!/usr/bin/env python3
"""Compare fixed configurations or adaptive inference against a captured baseline."""
import argparse
import json
import hashlib
from importlib.metadata import version
import platform
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.adapters import StressNgAdapter, SysbenchAdapter, HackbenchAdapter, CyclictestAdapter
from benchmarks.evaluation import compare_configs, compare_policies
from config.loader import build_registry_from_config
from safety import CheckpointManager, SecondaryValidator
from safety.session import TrainingSession
from scheduler import SchedulerController, Validator, Writer, RollbackStack, ProfileStore
from scheduler.backend import SysctlBackend
from scripts.run_training import _DryRunBackend, _DryRunBenchmark, _DryRunMonitor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates",
                        help='JSON file mapping method names to logical parameter/value maps')
    parser.add_argument("--output", required=True, help="New JSON report path")
    parser.add_argument("--config", default="config/scheduler.yaml")
    parser.add_argument("--params", nargs="*", default=None, help="Match the training registry subset")
    parser.add_argument("--model", help="SB3 model ZIP; compares inference against baseline/random")
    parser.add_argument("--algorithm", choices=["ppo", "sac"], default="ppo")
    parser.add_argument("--action-mode", choices=["discrete", "continuous"], default="discrete")
    parser.add_argument("--steps", type=int, default=5, help="Measurements per policy trajectory")
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--duration", type=int, default=5)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--benchmark", choices=["cpu", "memory", "mixed", "interactive"], default="cpu")
    parser.add_argument("--loops", type=int, default=1000, help="hackbench/cyclictest iterations")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--watchdog-timeout", type=float, default=120)
    args = parser.parse_args()
    if min(args.duration, args.workers, args.loops, args.steps) < 1 or args.repeats < 2:
        parser.error("duration/workers must be positive and repeats must be at least two")
    output = Path(args.output)
    raw_path = output.with_suffix(output.suffix + ".jsonl")
    if output.exists() or raw_path.exists():
        parser.error("Report paths already exist; choose a new --output")
    if not args.model and not args.candidates:
        parser.error("Provide --candidates, --model, or both")
    candidates = json.loads(Path(args.candidates).read_text()) if args.candidates else {}
    if not isinstance(candidates, dict) or {"baseline", "random", "policy"} & set(candidates):
        parser.error("candidates must be an object without reserved names baseline/random/policy")
    if not args.model and not candidates:
        parser.error("Provide at least one fixed candidate or a model")
    registry = build_registry_from_config(args.config, param_names=args.params)
    validator = Validator(registry)
    for params in candidates.values():
        if not isinstance(params, dict):
            parser.error("each candidate must be a parameter/value object")
        validator.validate(params)
    backend = _DryRunBackend(registry) if args.dry_run else SysctlBackend()
    adapters = {"cpu": StressNgAdapter, "memory": SysbenchAdapter,
                "mixed": HackbenchAdapter, "interactive": CyclictestAdapter}
    benchmark = _DryRunBenchmark(backend) if args.dry_run else adapters[args.benchmark]()
    if args.dry_run:
        benchmark.name = f"synthetic-{args.benchmark}"
        benchmark.workload_type = args.benchmark
    kwargs = {
        "cpu": {"timeout": args.duration, "workers": args.workers},
        "memory": {"timeout": args.duration, "threads": args.workers},
        "mixed": {"groups": args.workers, "loops": args.loops},
        "interactive": {"loops": args.loops},
    }[args.benchmark]
    controller = SchedulerController(
        registry, validator, Writer(registry, backend), RollbackStack(), ProfileStore(),
        secondary_validator=SecondaryValidator(),
    )
    checkpoint = CheckpointManager(
        str(output.with_suffix(".safety.json")) if args.dry_run else "data/safety_checkpoint.json"
    )
    random.seed(args.seed)
    model_metadata = None
    if args.model:
        model_path = Path(args.model)
        model_metadata = {"path": str(model_path), "sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
                          "algorithm": args.algorithm, "action_mode": args.action_mode}
    output.parent.mkdir(parents=True, exist_ok=True)
    with TrainingSession(controller, checkpoint, args.watchdog_timeout) as session:
        # Flush each raw result so an interrupted run still has inspectable data.
        with raw_path.open("x") as raw:
            def record(row):
                if session.watchdog.timed_out:
                    raise RuntimeError("Watchdog expired during evaluation")
                raw.write(json.dumps(row) + "\n")
                raw.flush()
                session.watchdog.ping()

            if args.model:
                from core.trainer import Trainer
                from monitor.collector import Monitor, default_sources
                from rl.env import LinuxSchedulerEnv
                if args.algorithm == "sac" and args.action_mode != "continuous":
                    parser.error("SAC requires --action-mode continuous")
                monitor = _DryRunMonitor(backend) if args.dry_run else Monitor(sources=default_sources(
                    sched_param_keys=tuple(meta.path for meta in registry.get_all())))
                env = LinuxSchedulerEnv(
                    controller, monitor, benchmark, registry, watchdog=session.watchdog,
                    episode_steps=args.steps, action_mode=args.action_mode,
                    benchmark_kwargs=kwargs,
                )
                trainer = Trainer.load(args.model, env, algorithm=args.algorithm)
                report = compare_policies(
                    env, {"policy": trainer.predict}, configs=candidates,
                    repeats=args.repeats, steps=args.steps, seed=args.seed, on_record=record,
                )
            else:
                report = compare_configs(
                    controller, benchmark, candidates, repeats=args.repeats, seed=args.seed,
                    benchmark_kwargs=kwargs,
                    on_record=record,
                )
        report.update({
            "dry_run": args.dry_run,
            "measurement_kind": "synthetic" if args.dry_run else "live benchmark",
            "platform": platform.platform(), "python": platform.python_version(),
            "benchmark": benchmark.name,
            "benchmark_kwargs": kwargs,
            "requested_workload": args.benchmark,
            "package_versions": {name: version(name) for name in (
                "numpy", "gymnasium", "stable-baselines3", "torch")},
            "candidates": candidates, "config_yaml": Path(args.config).read_text(),
            "registry": [{"name": m.name, "path": m.path} for m in registry.get_all()],
            "model": model_metadata,
            "scope": report.get("scope", "Fixed configuration comparison"),
        })
    output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report["summary"], indent=2))
    print(f"Report: {output} (synthetic={args.dry_run})")


if __name__ == "__main__":
    main()
