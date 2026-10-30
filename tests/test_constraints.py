"""Model kernel pair rejection to test both final values and write order."""
import pytest

from scheduler import (
    ParameterMeta, ParameterRegistry, SchedulerController, Validator,
    Writer, RollbackStack, ProfileStore,
)
from scheduler.exceptions import ValidationError, WriteError


class PairBackend:
    def __init__(self, lower, upper, exempt):
        self.lower, self.upper, self.exempt = lower, upper, exempt
        self.state = {lower: 80, upper: 100}
        self.writes = []

    def read(self, path):
        return str(self.state[path])

    def write(self, path, value):
        new = {**self.state, path: value}
        if new[self.lower] != self.exempt and new[self.lower] > new[self.upper]:
            raise WriteError("kernel rejected intermediate pair")
        self.state = new
        self.writes.append(path)


@pytest.fixture(params=[("sched_rt_runtime_us", "sched_rt_period_us", -1),
                       ("sched_util_clamp_min", "sched_util_clamp_max", None)])
def pair(request):
    lower, upper, exempt = request.param
    registry = ParameterRegistry()
    for name in (lower, upper):
        registry.register(ParameterMeta(name=name, path=f"kernel.{name}", type=int,
                                        min_value=-1 if exempt else 0, max_value=1024))
    backend = PairBackend(f"kernel.{lower}", f"kernel.{upper}", exempt)
    controller = SchedulerController(registry, Validator(registry), Writer(registry, backend),
                                     RollbackStack(), ProfileStore())
    return controller, backend, lower, upper


def test_pair_rejects_invalid_target_without_writes(pair):
    controller, backend, lower, upper = pair
    with pytest.raises(ValidationError):
        controller.apply_parameters({lower: 90, upper: 85})
    assert backend.writes == []


def test_lower_upper_increase_and_restore_order(pair):
    controller, backend, lower, upper = pair
    controller.apply_parameters({lower: 120, upper: 150})
    assert backend.writes == [f"kernel.{upper}", f"kernel.{lower}"]
    controller.rollback()
    assert backend.writes[-2:] == [f"kernel.{lower}", f"kernel.{upper}"]
    assert controller.read_state() == {lower: 80, upper: 100}


def test_decrease_orders_lower_first(pair):
    controller, backend, lower, upper = pair
    controller.apply_parameters({upper: 50, lower: 40})
    assert backend.writes == [f"kernel.{lower}", f"kernel.{upper}"]


def test_single_registered_parameter_checks_unregistered_counterpart(pair):
    controller, backend, lower, upper = pair
    registry = ParameterRegistry()
    registry.register(controller.registry.get(lower))
    subset = SchedulerController(registry, Validator(registry), Writer(registry, backend),
                                 RollbackStack(), ProfileStore())
    with pytest.raises(ValidationError):
        subset.apply_parameters({lower: 101})
    assert backend.writes == []
