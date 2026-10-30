"""Training lifecycle: capture, persist, watch, and restore a kernel baseline."""
from __future__ import annotations

import signal
from pathlib import Path

from safety.checkpoint import CheckpointManager
from safety.watchdog import Watchdog


class TrainingSession:
    """Restore on normal exit, exceptions, Ctrl-C, and SIGTERM.

    SIGKILL, process death and kernel hangs require explicit checkpoint
    recovery. A thread watchdog cannot provide out-of-process recovery.
    """

    def __init__(self, controller, checkpoint: CheckpointManager, timeout_sec=120.0):
        self.controller = controller
        self.checkpoint = checkpoint
        self.baseline = None
        self.watchdog = Watchdog(self._abort, timeout_sec=timeout_sec)

    def _abort(self):
        if self.baseline is not None:
            self.controller.halt_and_restore(self.baseline)

    def restore(self):
        if self.baseline is not None:
            self.controller.restore_state(self.baseline)

    def recover_saved(self):
        """Recover a previous session; never discard an invalid checkpoint."""
        with self.controller.exclusive():
            self._recover_saved()

    def _recover_saved(self):
        saved = self.checkpoint.load_checkpoint()
        metas = self.controller.registry.get_all()
        if set(saved) != {meta.path for meta in metas}:
            raise ValueError("Checkpoint does not match the complete registry; inspect it manually")
        state = {meta.name: meta.type(saved[meta.path]) for meta in metas}
        self.controller.restore_state(state)
        self.checkpoint.clear_checkpoint()

    def __enter__(self):
        self._lease = self.controller.exclusive()
        self._lease.__enter__()
        try:
            return self._enter()
        except BaseException:
            self._lease.__exit__(None, None, None)
            raise

    def _enter(self):
        if Path(self.checkpoint.checkpoint_path).exists():
            raise RuntimeError("Recovery checkpoint already exists; use --recover before training")
        self.baseline = self.controller.read_state()
        self.checkpoint.save_checkpoint({
            meta.path: self.baseline[meta.name]
            for meta in self.controller.registry.get_all()
        })
        self._previous_sigterm = signal.signal(signal.SIGTERM, self._terminate)
        self.watchdog.start()
        return self

    @staticmethod
    def _terminate(signum, frame):
        raise SystemExit(128 + signum)

    def __exit__(self, exc_type, exc, traceback):
        try:
            self.watchdog.stop()
            self.restore()
            # Retain the checkpoint if restore() raises, even on a clean exit.
            self.checkpoint.clear_checkpoint()
        finally:
            try:
                signal.signal(signal.SIGTERM, self._previous_sigterm)
            finally:
                self._lease.__exit__(None, None, None)
        return False
