"""Cross-parameter validity and write ordering for known sysctl pairs.

RT runtime/period: https://docs.kernel.org/scheduler/sched-rt-group.html
Utilisation clamps: https://docs.kernel.org/admin-guide/sysctl/kernel.html
These checks do not model cgroups, deadline admission or workload safety.
"""
from scheduler.exceptions import ValidationError


# (lower bound, upper bound, lower-bound value exempt from comparison)
PAIRS = (
    ("kernel.sched_rt_runtime_us", "kernel.sched_rt_period_us", -1),
    ("kernel.sched_util_clamp_min", "kernel.sched_util_clamp_max", None),
)


def ordered_update(registry, backends, params):
    """Reject invalid final pairs and order writes to keep intermediate pairs valid.

    Resolve an unregistered counterpart through the changed parameter's backend,
    so training on a one-parameter subset still checks the live counterpart.
    """
    names = list(params)
    by_path = {registry.get(name).path: name for name in names}
    for lower, upper, exempt in PAIRS:
        touched = set(by_path) & {lower, upper}
        if not touched:
            continue
        meta = registry.get(by_path[next(iter(touched))])
        backend = backends[meta.backend]
        current = {path: int(backend.read(path)) for path in (lower, upper)}
        target = dict(current)
        for path in touched:
            target[path] = int(params[by_path[path]])
        if target[lower] != exempt and target[lower] > target[upper]:
            raise ValidationError(f"{lower} must not exceed {upper}")
        if len(touched) == 2:
            # If the old lower value exceeds the new upper, lower it first.
            # Otherwise raising the upper first safely makes room for the lower.
            lower_first = current[lower] != exempt and current[lower] > target[upper]
            first, second = (lower, upper) if lower_first else (upper, lower)
            names.remove(by_path[first])
            names.remove(by_path[second])
            names.extend((by_path[first], by_path[second]))
    return {name: params[name] for name in names}
