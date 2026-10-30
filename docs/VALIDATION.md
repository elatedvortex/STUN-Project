# Validation record — 2026-10-31

This records checks actually performed during the hardening work. It does not
establish a performance improvement or production readiness.

## Automated checks

```bash
RUN_HOST_CHECKS=1 RUN_GUI_CHECKS=1 PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python -m pytest tests/ -q
```

Result: **200 passed in 8.09 seconds**, with no warnings. This includes:

- Partial writes, failed restores, retained recovery state and interruptions.
- Separate-process lease contention and lease release after process death.
- SIGKILL of a child with persistent fake backend state, followed by parent recovery.
- RT/uclamp final-value validation and intermediate write/restore ordering.
- Live sysctl reads, monitor data and a one-second, one-worker stress-ng run.
- Offscreen Qt window construction, snapshot delivery and worker shutdown in a
  temporary directory, with sysctl writes forbidden.
- Raw-score policy comparisons, continuous-action baseline behaviour, fixed
  configurations, paired intervals, and observation/path mapping regressions.

Default tests skip the three host checks and the offscreen Qt check unless their
environment flags are set. Dashboard checks require the optional GUI dependencies.

Dry-run CLI smoke checks also passed:

- Supervised PPO training for 256 steps, one evaluation episode, and model save.
- PPO inference comparison against baseline, random actions and a fixed candidate.
- SAC training for 32 steps and continuous-action inference comparison.
- Parameter sweep and single-cycle live tuner.

The SAC smoke run is shorter than its learning warmup; it checks the command
path and inference compatibility, not successful learning. All these CLI scores
are synthetic. Temporary outputs were kept outside project runtime data.

The package wheel builds with the new recovery/evaluation modules and YAML files.
Declared core dependency ranges were checked against the installed environment:
Python 3.14.7, NumPy 2.5.1, Gymnasium 1.3.0, Stable-Baselines3 2.9.0, Torch 2.13.0,
and pytest 9.1.1. Older supported combinations were not independently tested.

## Local host scope

Read-only preflight found all eight configured sysctl parameters readable on
Linux 7.2.3-arch1-3, x86_64, with 16 logical CPUs. The available stress-ng reported
0.22.00. CPU governors reported `powersave`, which matters when designing future
performance experiments. The configured values matched the initial readings
after all checks. No live sysctl writes or privileged tuning experiments ran.

## Still unverified

- Real kernel write failures and recovery, including cgroup/deadline admission.
- Long-running stability and supervisor failure scenarios on a dedicated test host.
- Policy performance across independently trained seeds, held-out workloads and machines.
- Application-level response time, workload-category accuracy, and proxy suitability.
- Process-scan overhead on large hosts and inference overhead.
- Every dashboard interaction and GUI training/sweep crash recovery.

The old presentation binaries remain historical, unverified artifacts.
See [EVALUATION.md](EVALUATION.md) for the commands, model retraining notice,
measurement limitations, and recovery boundaries.
