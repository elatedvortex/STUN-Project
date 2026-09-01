"""
dashboard/worker.py — Background QThread that polls the Monitor and emits
a SystemSnapshot every `interval_ms` milliseconds.

Design rules:
- Only the Worker thread ever calls monitor.read_snapshot().
- The GUI thread only connects to the `snapshot_ready` signal.
- The Worker owns the Monitor instance; the GUI constructs it and passes it in.
"""

from __future__ import annotations

import logging
import time

from PyQt6.QtCore import QThread, pyqtSignal

from monitor.collector import Monitor
from monitor.types import SystemSnapshot

logger = logging.getLogger(__name__)


class MonitorWorker(QThread):
    """Runs in a background thread; emits `snapshot_ready` at each tick."""

    snapshot_ready = pyqtSignal(object)   # carries a SystemSnapshot
    error_occurred = pyqtSignal(str)

    def __init__(self, monitor: Monitor, interval_ms: int = 1000) -> None:
        super().__init__()
        self._monitor = monitor
        self._interval_s = interval_ms / 1000.0
        self._running = False

    # ── public API ────────────────────────────────────────────────────────
    def stop(self) -> None:
        self._running = False

    # ── QThread override ──────────────────────────────────────────────────
    def run(self) -> None:
        self._running = True
        logger.info("MonitorWorker started (interval=%.1fs)", self._interval_s)
        try:
            self._monitor.check_capabilities()
        except Exception as exc:
            self.error_occurred.emit(f"Monitor capability check failed: {exc}")
            return

        while self._running:
            t0 = time.monotonic()
            try:
                snapshot = self._monitor.read_snapshot()
                self.snapshot_ready.emit(snapshot)
            except Exception as exc:  # noqa: BLE001
                logger.warning("MonitorWorker: read_snapshot raised %s", exc)
                self.error_occurred.emit(str(exc))

            elapsed = time.monotonic() - t0
            sleep_for = max(0.0, self._interval_s - elapsed)
            # Sleep in small slices so stop() is noticed quickly
            deadline = time.monotonic() + sleep_for
            while self._running and time.monotonic() < deadline:
                time.sleep(0.05)

        logger.info("MonitorWorker stopped")
