import pytest
from unittest.mock import MagicMock, patch
from scheduler import (
    ParameterMeta,
    ParameterRegistry,
    Validator,
    Writer,
    RollbackStack,
    ProfileStore,
    SchedulerController,
    SchedulerBackend,
    ValidationError,
    ParameterNotFoundError,
    WriteError,
    ReadbackError
)

class FakeBackend(SchedulerBackend):
    def __init__(self):
        self.state = {}

    def write(self, path: str, value: any) -> None:
        if "error" in path:
            raise WriteError(f"Mock error writing to {path}")
        self.state[path] = str(value)

    def read(self, path: str) -> any:
        if path not in self.state:
            return "0"
        return self.state[path]

@pytest.fixture
def registry():
    reg = ParameterRegistry()
    reg.register(ParameterMeta(name="sched_min_granularity_ns", type=int, min_value=100000, max_value=100000000, backend="sysctl", path="kernel.sched_min_granularity_ns"))
    reg.register(ParameterMeta(name="sched_wakeup_granularity_ns", type=int, min_value=100000, max_value=100000000, backend="sysctl", path="kernel.sched_wakeup_granularity_ns"))
    return reg

@pytest.fixture
def fake_backend():
    return FakeBackend()

def test_registry_register_and_get(registry):
    param = registry.get("sched_min_granularity_ns")
    assert param.name == "sched_min_granularity_ns"
    assert param.type == int

def test_registry_get_not_found(registry):
    with pytest.raises(ParameterNotFoundError):
        registry.get("invalid_param")

def test_validator_valid(registry):
    val = Validator(registry)
    val.validate({"sched_min_granularity_ns": 3000000})

def test_validator_invalid_bounds(registry):
    val = Validator(registry)
    with pytest.raises(ValidationError, match="less than min"):
        val.validate({"sched_min_granularity_ns": 10})

    with pytest.raises(ValidationError, match="greater than max"):
        val.validate({"sched_min_granularity_ns": 200000000})

def test_validator_invalid_type(registry):
    val = Validator(registry)
    with pytest.raises(ValidationError):
        val.validate({"sched_min_granularity_ns": "not-an-int"})

def test_writer_write_and_verify(registry, fake_backend):
    writer = Writer(registry, backend=fake_backend)
    writer.write_and_verify("sched_min_granularity_ns", 3000000)
    assert fake_backend.state["kernel.sched_min_granularity_ns"] == "3000000"

def test_writer_readback_error(registry):
    class BadFakeBackend(FakeBackend):
        def read(self, path: str) -> any:
            return "9999" # Always return wrong value
            
    writer = Writer(registry, backend=BadFakeBackend())
    with pytest.raises(ReadbackError):
        writer.write_and_verify("sched_min_granularity_ns", 3000000)

def test_controller_apply_and_rollback(registry, fake_backend):
    validator = Validator(registry)
    writer = Writer(registry, backend=fake_backend)
    rollback_stack = RollbackStack()
    profile_store = ProfileStore()
    
    controller = SchedulerController(registry, validator, writer, rollback_stack, profile_store)
    
    # Initial state
    fake_backend.state["kernel.sched_min_granularity_ns"] = "1000000"
    
    # Apply
    controller.apply_parameters({"sched_min_granularity_ns": 3000000})
    assert fake_backend.state["kernel.sched_min_granularity_ns"] == "3000000"
    assert len(rollback_stack._stack) == 1
    
    # Rollback
    controller.rollback()
    assert fake_backend.state["kernel.sched_min_granularity_ns"] == "1000000"
    assert len(rollback_stack._stack) == 0

def test_profile_store(registry, fake_backend):
    validator = Validator(registry)
    writer = Writer(registry, backend=fake_backend)
    rollback_stack = RollbackStack()
    profile_store = ProfileStore()
    
    controller = SchedulerController(registry, validator, writer, rollback_stack, profile_store)
    
    profile_store.save_profile("latency", {"sched_min_granularity_ns": 100000})
    controller.apply_profile("latency")
    
    assert fake_backend.state["kernel.sched_min_granularity_ns"] == "100000"

