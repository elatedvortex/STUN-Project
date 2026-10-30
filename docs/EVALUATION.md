# Evidence and evaluation

This repository is an experimental scheduler tuning framework. Unit tests and
synthetic training demonstrate software behaviour, not real performance gains.
The historical presentation numbers are unverified illustrative values. Existing
PPTX/PNG artifacts have not been regenerated; do not cite them as measurements.
The v7–v9 templates and standalone results chart generator now disclose this.

## Repeated comparisons

Choose fixed configurations using separate training/sweep runs, then evaluate
them on held-out runs. Create a JSON file using logical registry parameter names:

```json
{
  "sweep_selected": {"sched_rr_timeslice_ms": 100},
  "random_selected": {"sched_rr_timeslice_ms": 150}
}
```

The names describe how **you** selected the configurations. The evaluator does
not train a model or run a search. The optional `--model` mode evaluates an adaptive policy. Give methods
equal tuning budgets, record their selection procedure, and include the default
baseline. A baseline is the machine's captured starting state; reset the machine
to your intended defaults before calling it a default Linux baseline.

```bash
# Exercise reporting and recovery with synthetic scores; no kernel writes.
python scripts/run_evaluation.py --dry-run --candidates candidates.json \
  --repeats 10 --seed 42 --output /tmp/synthetic-evaluation.json

# Live stress-ng measurement; writes the configured sysctl parameters.
python scripts/run_evaluation.py --candidates candidates.json \
  --repeats 20 --duration 10 --workers 2 --output data/evaluation/run-001.json
```

Each repeat shuffles method order, restores the captured baseline between trials,
and records actual parameter readbacks and raw benchmark output. The report
includes mean/standard deviation, failure counts (total minus successful runs),
paired improvement percentages, platform, seed and configuration. JSONL is flushed
after each trial so partial results survive interruption. Positive improvement
means better for either score direction. Failed pairs are excluded and counted;
inspect failures rather than reporting only successful averages. Standard
deviation describes variability. The report also provides a percentile bootstrap
95% interval for the **mean paired improvement**, when at least three valid pairs
exist. Small samples, correlated repeats and workload drift limit its usefulness;
it is not a guarantee or a substitute for independent sessions.

Use the same hardware, kernel, benchmark version, power settings, workload command
and worker count for every method. Record these details along with background
load, cooling/warmup procedure, and training seeds. Repeat across independent
sessions and workloads before making broad claims. Select `--benchmark cpu|memory|mixed|interactive` for stress-ng, sysbench memory,
hackbench elapsed time, or cyclictest maximum latency. `--duration` controls CPU
and memory runs; `--loops` controls hackbench/cyclictest iterations, with
`--workers` selecting CPU workers, memory threads, or hackbench groups. Cyclictest
may require additional privileges. The adapters are proxies, not measurements
of application response time. IO, inference overhead and kernel stability remain
outside this evaluator. Retain the report and raw
JSONL alongside every published result. Report live and synthetic data separately.

## Recovery boundaries

The controller serialises applies and restores. Failed writes restore their
pre-transaction state; failed restores retain history, try the other saved values,
and block further tuning. Kernel writes are sequential, not an atomic transaction.
The controller checks RT runtime <= period (with the kernel's unlimited sentinel)
and utilisation-clamp min <= max, and orders paired writes/restores to avoid
invalid intermediate values. It reads unregistered counterparts for subset
training. Other kernel/cgroup admission constraints can still reject changes.
See [RT scheduler documentation](https://docs.kernel.org/scheduler/sched-rt-group.html)
and the [uclamp handler](https://github.com/torvalds/linux/blob/master/kernel/sched/core.c).

The training, sweep, and live-tuner CLIs capture every registered starting value and persists a recovery
checkpoint before training. It restores on normal exit, exceptions, Ctrl-C and
SIGTERM. The checkpoint is removed only after verified restoration. Existing
checkpoints block new sessions so an unresolved baseline is not overwritten.

```bash
# Must use the same registry/config/subset as the interrupted run.
python scripts/run_training.py --recover --config config/scheduler.yaml
```

Use `--safety-checkpoint PATH` for a custom training checkpoint. Dry-run training
uses a separate checkpoint under its model output directory. Live evaluation
shares `data/safety_checkpoint.json` with live training, recoverable with the same
command. Live controllers acquire an advisory host lease at
`/tmp/rl-scheduler-framework.host.lock`; these CLI sessions hold it through final
restoration. A second cooperating controller fails rather than interleaving
writes. The lease is released by the OS on process death and the file is never
unlinked. It cannot stop external sysctl writers, coordinate hosts with separate
`/tmp` namespaces, or turn legacy controller calls into full recovery sessions.

The watchdog timeout includes benchmark time and model updates. Choose
`--watchdog-timeout` above the longest expected interval between completed steps
(default 120 seconds). A timeout halts controller applies and attempts baseline
restoration. A Python thread cannot recover from SIGKILL, process death, kernel
hangs, or a blocked backend call. Use `--supervised` on the training CLI to run
a separate parent that attempts checkpoint recovery after child exit/death,
including SIGKILL. The supervisor must survive, retain permissions, and be able
to reach the backend; it cannot recover a hung kernel or processes that escape
the child's process group. Unsupervised process death still needs manual recovery.
Bounds validation alone does not establish that a parameter set is safe or useful
for every workload. Live **write/recovery** validation and long-running stability
tests remain outstanding; opt-in read-only host checks are available.

## Adaptive inference comparison

```bash
python scripts/run_training.py --dry-run --supervised --timesteps 256 \
  --eval-episodes 1 --checkpoint-dir /tmp/rl-models
python scripts/run_evaluation.py --dry-run --model /tmp/rl-models/ppo_final.zip \
  --candidates candidates.json --steps 5 --repeats 10 \
  --output /tmp/policy-comparison.json
```

Model mode compares deterministic policy inference, seeded random **actions**,
the unchanged baseline, and any supplied fixed configurations. This random
baseline is not a tuned random-search configuration; select that separately on
training data and pass it through `--candidates`. Match `--algorithm`,
`--action-mode`, config, and `--params` subset to training. SAC needs continuous
actions. Reports include the model hash, installed library versions, action
trajectories, rejected actions, and raw scores. Each method resets to the same
baseline and gets the same measurement count. Rewards are reset between methods
and are not used as performance scores. A repeat's mean raw score is the unit of
comparison, so correlated steps are not counted as independent repeats. These
scores do not include benchmark wall time or inference overhead.

## Workload evidence

The process source scans counters for all visible processes, then returns the
busiest capped sample by **interval** CPU ticks. Startup/new processes need a
second observation; PID start times prevent reusing another process's counters.
Scanning cost grows with process count and needs overhead testing on large hosts.
Legacy snapshots without interval ticks are labelled lifetime estimates.
The live tuner skips samples with no measured activity or less than 50% of sampled
CPU ticks attributable to recognised names. This is a conservative heuristic,
not calibrated classification confidence. Name matching and the mapping from
application categories to benchmarks still need application-specific validation.

## Read-only host integration

```bash
python scripts/check_host.py --output /tmp/host-compatibility.json
RUN_HOST_CHECKS=1 python -m pytest tests/test_host_integration.py -q
```

The report records kernel/tool versions, parameter availability and CPU governors.
The opt-in tests read sysctls and monitor data and run a one-second, one-worker CPU
benchmark. They never write sysctls. These checks establish local compatibility,
not tuning safety, general performance gains, or long-term stability.

## Observation correction and existing models

Scheduler values from live monitor sources use sysctl paths. The state builder
now accepts those paths as well as legacy logical names; the earlier lookup
silently produced zero-valued parameter observations. Training also requests all
registered keys, and its synthetic monitor exposes backend values. Profile
distance now handles path-keyed history correctly. **Retrain previously saved
models before relying on them:** the observation dimensions are unchanged but
these inputs now carry the actual values. Matching dimensions alone does not
establish compatibility with old training semantics.

Library sweeps hold a host lease for the complete search and restore their
starting state even after an interruption. CLI sweeps additionally persist the
baseline checkpoint. GUI/library use without a `TrainingSession` still lacks
persistent crash recovery; the lease alone does not provide it.

An offscreen dashboard lifecycle check is available with dashboard dependencies:

```bash
RUN_GUI_CHECKS=1 python -m pytest tests/test_dashboard_smoke.py -q
```

It checks window construction, real monitor delivery and worker shutdown in a
temporary directory, with sysctl writes forbidden. It does not test every panel
interaction or long-running training in the GUI.
