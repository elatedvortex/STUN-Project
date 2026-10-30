"""Linux advisory lease shared by cooperating scheduler controllers."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat
import tempfile
import threading


DEFAULT_LOCK_PATH = Path(tempfile.gettempdir()) / "rl-scheduler-framework.host.lock"


class HostLease:
    """Hold flock across an entire session, with nesting for its controller.

    Separate controller instances use separate descriptors, so a second
    controller cannot enter another one's session even in the same process.
    The lock file is never unlinked: deleting it would allow a second inode
    to be locked while the original owner is still active.
    """

    def __init__(self, path=DEFAULT_LOCK_PATH):
        self.path = Path(path)
        self._mutex = threading.Lock()
        self._depth = 0
        self._fd = None

    @contextmanager
    def hold(self):
        with self._mutex:
            if self._depth == 0:
                fd = os.open(self.path, os.O_RDONLY | os.O_CREAT | os.O_NOFOLLOW, 0o644)
                try:
                    if not stat.S_ISREG(os.fstat(fd).st_mode):
                        raise RuntimeError("Scheduler lease must be a regular file")
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    os.close(fd)
                    raise RuntimeError("Another scheduler controller holds the host lease") from exc
                except BaseException:
                    os.close(fd)
                    raise
                self._fd = fd
            self._depth += 1
        try:
            yield
        finally:
            with self._mutex:
                self._depth -= 1
                if self._depth == 0:
                    os.close(self._fd)
                    self._fd = None
