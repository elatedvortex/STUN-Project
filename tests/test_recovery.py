"""Failure injection against real controller/session code; no kernel writes."""
import signal

import pytest

from scheduler import (
    ParameterMeta, ParameterRegistry, SchedulerController, Validator,
    Writer, RollbackStack, ProfileStore,
)
from scheduler.exceptions import WriteError, RecoveryError
from safety.checkpoint import CheckpointManager
from safety.session import TrainingSession
from core.loop import EpisodeRunner


class Backend:
    def __init__(self):
        self.state = {"kernel.a": "10", "kernel.b": "20"}
        self.failures = set()

    def read(self, path):
        return self.state[path]

    def write(self, path, value):
        if (path, value) in self.failures:
            raise WriteError("injected failure")
        self.state[path] = str(value)


@pytest.fixture
def system():
    registry = ParameterRegistry()
    for name in ("a", "b"):
        registry.register(ParameterMeta(
            name=name, path=f"kernel.{name}", type=int, min_value=0, max_value=100,
        ))
    backend = Backend()
    controller = SchedulerController(
        registry, Validator(registry), Writer(registry, backend),
        RollbackStack(), ProfileStore(),
    )
    return controller, backend


def test_partial_write_restores_entire_transaction(system):
    controller, backend = system
    backend.failures.add(("kernel.b", 40))
    with pytest.raises(WriteError):
        controller.apply_parameters({"a": 30, "b": 40})
    assert controller.read_state() == {"a": 10, "b": 20}
    assert controller.rollback_stack.peek() == {}


def test_watchdog_halt_prevents_further_writes_after_successful_restore(system):
    controller, _ = system
    baseline = controller.read_state()
    controller.apply_parameters({"a": 30})
    controller.halt_and_restore(baseline)
    with pytest.raises(RecoveryError, match="halted"):
        controller.apply_parameters({"a": 50})
    assert controller.read_state() == baseline


def test_failed_restore_keeps_history_and_blocks_writes(system):
    controller, backend = system
    controller.apply_parameters({"a": 30, "b": 40})
    backend.failures.add(("kernel.a", 10))
    with pytest.raises(RecoveryError):
        controller.rollback()
    assert controller.rollback_stack.peek() == {"a": 10, "b": 20}
    assert backend.state["kernel.b"] == "20"  # remaining restores still attempted
    with pytest.raises(RecoveryError):
        controller.apply_parameters({"b": 50})
    backend.failures.clear()
    controller.rollback()
    assert controller.read_state() == {"a": 10, "b": 20}


@pytest.mark.parametrize("failure", [None, RuntimeError, KeyboardInterrupt, SystemExit])
def test_session_restores_on_every_exit(system, tmp_path, failure):
    controller, _ = system
    checkpoint = CheckpointManager(str(tmp_path / "recovery.json"))
    session = TrainingSession(controller, checkpoint)

    def run():
        with session:
            controller.apply_parameters({"a": 30})
            controller.apply_parameters({"b": 40})
            if failure:
                raise failure()

    if failure:
        with pytest.raises(failure):
            run()
    else:
        run()
    assert controller.read_state() == {"a": 10, "b": 20}
    assert not session.watchdog.running
    assert checkpoint.load_checkpoint() == {}


def test_session_retains_checkpoint_until_recovery_verified(system, tmp_path):
    controller, backend = system
    checkpoint = CheckpointManager(str(tmp_path / "recovery.json"))
    with pytest.raises(RecoveryError):
        with TrainingSession(controller, checkpoint):
            controller.apply_parameters({"a": 30})
            backend.failures.add(("kernel.a", 10))
    assert checkpoint.load_checkpoint() == {"kernel.a": 10, "kernel.b": 20}
    with pytest.raises(RuntimeError, match="already exists"):
        with TrainingSession(controller, checkpoint):
            pass
    backend.failures.clear()
    TrainingSession(controller, checkpoint).recover_saved()
    assert controller.read_state() == {"a": 10, "b": 20}
    assert checkpoint.load_checkpoint() == {}


def test_checkpoint_write_error_prevents_training(system, tmp_path, monkeypatch):
    controller, _ = system
    checkpoint = CheckpointManager(str(tmp_path / "recovery.json"))

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr("safety.checkpoint.os.replace", fail)
    with pytest.raises(OSError):
        with TrainingSession(controller, checkpoint):
            pytest.fail("must not enter without a persisted checkpoint")


def test_sigterm_handler_restores_and_is_uninstalled(system, tmp_path):
    controller, _ = system
    checkpoint = CheckpointManager(str(tmp_path / "recovery.json"))
    original = signal.getsignal(signal.SIGTERM)
    with pytest.raises(SystemExit):
        with TrainingSession(controller, checkpoint):
            controller.apply_parameters({"a": 30})
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
    assert controller.read_state()["a"] == 10
    assert signal.getsignal(signal.SIGTERM) == original


def test_episode_runner_closes_on_step_failure():
    from unittest.mock import MagicMock
    env, agent, watchdog = MagicMock(), MagicMock(), MagicMock()
    env.reset.return_value = (None, {})
    env.step.side_effect = RuntimeError("benchmark failed")
    with pytest.raises(RuntimeError):
        EpisodeRunner(env, agent, watchdog).run_episode()
    env.close.assert_called_once()
    watchdog.stop.assert_called_once()
