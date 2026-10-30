import json
from pathlib import Path
import signal
import sys

import pytest

from safety.checkpoint import CheckpointManager
from safety.session import TrainingSession
from safety.supervisor import run_supervised
from tests.test_recovery import system


def test_parent_recovers_persistent_backend_after_child_sigkill(system, tmp_path):
    controller, _ = system
    state_file = tmp_path / "backend.json"
    state_file.write_text(json.dumps({"kernel.a": 10, "kernel.b": 20}))
    checkpoint = CheckpointManager(str(tmp_path / "recovery.json"))

    class FileBackend:
        def read(self, path):
            return json.loads(state_file.read_text())[path]

        def write(self, path, value):
            state = json.loads(state_file.read_text())
            state[path] = value
            state_file.write_text(json.dumps(state))

    controller.writer.backends["sysctl"] = FileBackend()
    child = """
import json, os, signal, sys
from pathlib import Path
from safety.checkpoint import CheckpointManager
state = Path(sys.argv[1])
CheckpointManager(sys.argv[2]).save_checkpoint(json.loads(state.read_text()))
state.write_text(json.dumps({'kernel.a': 30, 'kernel.b': 40}))
os.kill(os.getpid(), signal.SIGKILL)
"""
    status = run_supervised(
        [sys.executable, "-B", "-c", child, str(state_file), checkpoint.checkpoint_path],
        TrainingSession(controller, checkpoint).recover_saved,
    )
    assert status == -signal.SIGKILL
    assert controller.read_state() == {"a": 10, "b": 20}
    assert not Path(checkpoint.checkpoint_path).exists()


def test_supervisor_does_not_hide_recovery_failure():
    def recover():
        raise RuntimeError("restore failed")

    with pytest.raises(RuntimeError, match="restore failed"):
        run_supervised([sys.executable, "-c", "pass"], recover)
