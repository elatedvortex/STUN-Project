import subprocess
import sys

import pytest

from safety.lease import HostLease
from safety.checkpoint import CheckpointManager
from safety.session import TrainingSession
from tests.test_recovery import system


def test_independent_controllers_cannot_share_lease(tmp_path):
    first, second = HostLease(tmp_path / "lease"), HostLease(tmp_path / "lease")
    with first.hold():
        with first.hold():
            with pytest.raises(RuntimeError, match="Another scheduler"):
                with second.hold():
                    pytest.fail("must not acquire")
        with pytest.raises(RuntimeError):
            with second.hold():
                pytest.fail("nested exit must not release outer lease")
    with second.hold():
        pass


def test_process_death_releases_lease(tmp_path):
    path = tmp_path / "lease"
    code = """
import sys
from safety.lease import HostLease
with HostLease(sys.argv[1]).hold():
    print('ready', flush=True)
    sys.stdin.read()
"""
    child = subprocess.Popen([sys.executable, "-B", "-c", code, str(path)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        import select
        assert select.select([child.stdout], [], [], 5)[0], "child did not acquire lease"
        assert child.stdout.readline().strip() == "ready"
        with pytest.raises(RuntimeError):
            with HostLease(path).hold():
                pytest.fail("lease already held in another process")
        child.kill()
        child.wait(timeout=5)
        with HostLease(path).hold():
            pass
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=5)


def test_failed_session_entry_releases_host_lease(system, tmp_path):
    controller, _ = system
    controller._host_lease = HostLease(tmp_path / "lease")
    checkpoint = CheckpointManager(str(tmp_path / "recovery.json"))
    checkpoint.save_checkpoint({"unresolved": 1})
    with pytest.raises(RuntimeError, match="already exists"):
        with TrainingSession(controller, checkpoint):
            pass
    with HostLease(tmp_path / "lease").hold():
        pass
