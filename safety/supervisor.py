"""Optional parent process that attempts recovery after its child exits."""
import os
import signal
import subprocess


def run_supervised(command, recover):
    """Run an argv list without a shell; clean up the group before recovery.

    The supervisor must remain alive. It cannot recover a hung kernel or
    terminate processes that have escaped the child's process group.
    Recovery exceptions propagate so a failed restore never looks successful.
    """
    child = subprocess.Popen(command, start_new_session=True)
    try:
        return child.wait()
    finally:
        try:
            # Include benchmark children that might outlive the training process.
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()
        recover()
