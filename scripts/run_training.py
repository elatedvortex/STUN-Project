#!/usr/bin/env python3
"""
M4 training script — trains PPO or SAC on LinuxSchedulerEnv.

Usage
-----
  # Dry-run (fake env, 1000 steps, PPO)
  python3 scripts/run_training.py --dry-run --timesteps 1000

  # Real run with stress-ng reward signal (requires root / CAP_SYS_ADMIN)
  python3 scripts/run_training.py --algorithm sac --action-mode continuous \\
      --timesteps 50000 --checkpoint-freq 5000

  # Resume from checkpoint
  python3 scripts/run_training.py --dry-run --load data/checkpoints/ppo_500_steps.zip
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from monitor.types import SystemSnapshot
from monitor.collector import Monitor, default_sources
from benchmarks.types import BenchmarkResult
from benchmarks.base import BenchmarkRunner
from benchmarks.adapters import StressNgAdapter
from scheduler import (
    ParameterMeta, ParameterRegistry,
    Validator, Writer, RollbackStack, ProfileStore,
    SchedulerController, SchedulerBackend,
)
from safety import SecondaryValidator, CheckpointManager
from safety.session import TrainingSession
from rl.env import LinuxSchedulerEnv
from core.trainer import Trainer
from config.loader import build_registry_from_config


# ---------------------------------------------------------------------------
# Dry-run stubs
# ---------------------------------------------------------------------------

class _DryRunBackend(SchedulerBackend):
    def __init__(self, registry: ParameterRegistry):
        # Seed state from registry midpoints for a realistic starting point
        self.state = {}
        for p in registry.get_all():
            lo = float(p.min_value) if p.min_value is not None else 0.0
            hi = float(p.max_value) if p.max_value is not None else 1.0
            self.state[p.path] = str(p.type((lo + hi) / 2.0))

    def write(self, path, value): self.state[path] = str(value)
    def read(self, path): return self.state.get(path, "0")


class _DryRunMonitor:
    def __init__(self, backend=None):
        self._backend = backend

    def read_snapshot(self):
        import random
        return SystemSnapshot(
            timestamp=datetime.now(timezone.utc),
            cpu_util_pct=45.0 + random.gauss(0, 5),
            load_avg_1=1.2, load_avg_5=1.0,
            mem_util_pct=35.0, ctxt_switches_delta=50_000, runnable_procs=3,
            sched_params=({path: float(value) for path, value in self._backend.state.items()}
                          if self._backend is not None else {}),
        )


class _DryRunBenchmark(BenchmarkRunner):
    """Dry-run benchmark that responds to parameter changes.

    The score is a function of the current parameter values so the agent
    has a *learnable* signal — unlike the previous version which returned
    near-constant noise, making reward ≈ 0 (§2.1).
    """

    def __init__(self, backend: _DryRunBackend):
        super().__init__(name="dry-run", workload_type="cpu")
        self._backend = backend

    def run(self, **kwargs):
        import random
        # Compute a score that depends on actual parameter values so that
        # PPO has a non-trivial gradient to follow.
        total = 0.0
        n = 0
        for path, raw in self._backend.state.items():
            try:
                total += float(raw)
                n += 1
            except (ValueError, TypeError):
                pass
        # Normalise to a 0-200 range with noise
        base = (total / max(n, 1)) / 1e6  # scale down large ns values
        score = 100.0 + base * 10.0 + random.gauss(0, 2)
        return BenchmarkResult(self.name, self.workload_type, True, score, True, {"ops": score})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="M4 RL training")
    parser.add_argument("--algorithm", choices=["ppo", "sac"], default="ppo")
    parser.add_argument("--action-mode", choices=["discrete", "continuous"], default="discrete")
    parser.add_argument("--timesteps", type=int, default=10_000)
    parser.add_argument("--checkpoint-freq", type=int, default=1_000)
    parser.add_argument("--checkpoint-dir", default="data/checkpoints")
    parser.add_argument("--eval-episodes", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--watchdog-timeout", type=float, default=120.0,
                        help="Maximum seconds between completed steps (include benchmark and model updates)")
    parser.add_argument("--safety-checkpoint", default=None)
    parser.add_argument("--recover", action="store_true", help="Restore a saved baseline and exit")
    parser.add_argument("--supervised", action="store_true",
                        help="Use a parent process to attempt checkpoint recovery after child death")
    parser.add_argument("--load", default=None, help="Resume from checkpoint .zip")
    parser.add_argument("--config", default="config/scheduler.yaml",
                        help="Path to scheduler YAML config (§5.1)")
    parser.add_argument("--params", nargs="*", default=None,
                        help="Subset of param names to train on (default: all)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    log = logging.getLogger("run_training")

    # Auto-fix action mode for SAC
    if args.algorithm == "sac" and args.action_mode == "discrete":
        log.warning("SAC requires continuous actions — overriding --action-mode to continuous")
        args.action_mode = "continuous"

    # ── Registry from unified YAML config (§5.1, §5.2) ───────────────
    registry = build_registry_from_config(args.config, param_names=args.params)
    log.info("Registry loaded: %d params from %s", len(registry.get_all()), args.config)

    # ── Safety module wiring (§1.1, §1.2, §1.4) ─────────────────────
    secondary_validator = SecondaryValidator()
    checkpoint_path = args.safety_checkpoint or (
        str(Path(args.checkpoint_dir) / "dry_run_safety_checkpoint.json")
        if args.dry_run else "data/safety_checkpoint.json"
    )
    checkpoint_mgr = CheckpointManager(checkpoint_path)

    # ── Backend selection (§8.1 — removed `or True` hack) ────────────
    if args.dry_run:
        log.info("Using dry-run backend (no real sysctl writes)")
        backend = _DryRunBackend(registry)
        monitor = _DryRunMonitor(backend)
        benchmark = _DryRunBenchmark(backend)
    else:
        log.info("Using REAL sysctl backend — requires root / CAP_SYS_ADMIN")
        from scheduler.backend import SysctlBackend
        backend = SysctlBackend()
        monitor = Monitor(sources=default_sources(
            sched_param_keys=tuple(meta.path for meta in registry.get_all())))
        monitor.check_capabilities()
        benchmark = StressNgAdapter()

    # ── Controller with full safety pipeline (§1.1, §3.1) ────────────
    controller = SchedulerController(
        registry, Validator(registry), Writer(registry, backend=backend),
        RollbackStack(), ProfileStore(),
        secondary_validator=secondary_validator,
    )
    session = TrainingSession(controller, checkpoint_mgr, args.watchdog_timeout)
    if args.supervised and not args.recover:
        from safety.supervisor import run_supervised
        if Path(checkpoint_path).exists():
            raise RuntimeError("Recover the existing checkpoint before starting supervised training")

        def recover_child():
            if Path(checkpoint_path).exists():
                log.warning("Child left a recovery checkpoint; restoring saved baseline")
                session.recover_saved()

        command = [sys.executable, str(Path(__file__).resolve()),
                   *(argument for argument in sys.argv[1:] if argument != "--supervised")]
        status = run_supervised(command, recover_child)
        raise SystemExit(128 - status if status < 0 else status)
    if args.recover:
        session.recover_saved()
        log.info("Saved baseline restored and verified")
        return

    with session:
        env = LinuxSchedulerEnv(
            controller=controller, monitor=monitor, benchmark=benchmark,
            registry=registry, episode_steps=20, action_mode=args.action_mode,
            watchdog=session.watchdog,
        )

        checkpoint_dir = Path(args.checkpoint_dir)

        # SB3 algo kwargs
        algo_kwargs = {}
        if args.algorithm == "ppo":
            algo_kwargs = {"n_steps": 256, "batch_size": 64, "n_epochs": 4}
        elif args.algorithm == "sac":
            algo_kwargs = {"learning_starts": 256, "batch_size": 64}

        if args.load:
            log.info("Resuming from %s", args.load)
            trainer = Trainer.load(args.load, env, algorithm=args.algorithm, checkpoint_dir=checkpoint_dir)
        else:
            trainer = Trainer(
                env, algorithm=args.algorithm,
                checkpoint_dir=checkpoint_dir,
                **algo_kwargs,
            )

        log.info("Starting training: %s, %d timesteps", args.algorithm, args.timesteps)
        result = trainer.train(
            total_timesteps=args.timesteps,
            checkpoint_freq=args.checkpoint_freq,
            eval_episodes=args.eval_episodes,
        )

        # Save final model
        final_path = checkpoint_dir / f"{args.algorithm}_final"
        trainer.save(final_path)

        print("\n--- Training Summary ---")
        print(f"  algorithm        {result.algorithm}")
        print(f"  timesteps        {result.total_timesteps}")
        print(f"  elapsed          {result.elapsed_sec:.1f}s")
        print(f"  mean_reward      {result.mean_reward:.4f}")
        print(f"  std_reward       {result.std_reward:.4f}")
        print(f"  checkpoints      {result.checkpoint_dir}")
        print(f"  final model      {final_path}.zip")



if __name__ == "__main__":
    main()
