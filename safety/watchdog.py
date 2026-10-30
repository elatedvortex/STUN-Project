import threading
import time
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class Watchdog:
    """Runs in a separate thread and forces a rollback if not pinged within a timeout.

    Thread-safety: ``_last_ping`` and ``_running`` are guarded by a
    ``threading.Lock`` so the watchdog is safe under free-threaded Python
    (PEP-703 / 3.13+) as well as alternative runtimes like PyPy (§1.3).
    """

    def __init__(self, rollback_callback: Callable[[], None], timeout_sec: float = 10.0):
        self.rollback_callback = rollback_callback
        self.timeout_sec = timeout_sec
        if timeout_sec <= 0:
            raise ValueError("timeout_sec must be positive")
        self._lock = threading.Lock()
        self._last_ping = time.monotonic()
        self._timed_out = False
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def ping(self) -> None:
        with self._lock:
            self._last_ping = time.monotonic()

    @property
    def timed_out(self) -> bool:
        with self._lock:
            return self._timed_out

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._timed_out = False
            self._last_ping = time.monotonic()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False
        if self._thread:
            self._thread.join(timeout=self.timeout_sec + 1)

    def _run(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break
                elapsed = time.monotonic() - self._last_ping
                if elapsed > self.timeout_sec:
                    self._timed_out = True
            if elapsed > self.timeout_sec:
                logger.error(
                    "Watchdog timeout (%ss)! Forcing rollback.", self.timeout_sec,
                )
                try:
                    self.rollback_callback()
                except Exception:
                    logger.exception("Watchdog rollback_callback raised an exception")
                with self._lock:
                    self._running = False
                break
            time.sleep(min(0.1, self.timeout_sec / 2))
