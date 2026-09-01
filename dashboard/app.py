"""
dashboard/app.py — Main application window.

Layout
------
  ┌─────────────────────────────────────────────────────────────┐
  │  ● SysWatch    [CPU: 42%] [MEM: 61%] [▶ Running]  [■ Stop] │  ← header bar
  ├─────────────────────────────────────────────────────────────┤
  │  [ Overview │ Processes │ Memory │ Scheduler ]              │  ← tab bar
  │                                                             │
  │   <panel content>                                           │
  │                                                             │
  └─────────────────────────────────────────────────────────────┘
  │ Status bar: last update timestamp + source count            │
  └─────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import sys
import logging
from datetime import datetime, timezone

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon, QColor, QPalette
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QSizePolicy, QStatusBar, QTabWidget, QVBoxLayout, QWidget,
)

from dashboard import theme
from dashboard.panels.memory import MemoryPanel
from dashboard.panels.overview import OverviewPanel
from dashboard.panels.processes import ProcessPanel
from dashboard.panels.scheduler import SchedulerPanel
from dashboard.worker import MonitorWorker
from monitor.collector import Monitor, default_sources
from monitor.types import SystemSnapshot
from scheduler.controller import SchedulerController
from scheduler.profile import ProfileStore
from scheduler.registry import ParameterRegistry
from scheduler.rollback import RollbackStack
from scheduler.validator import Validator
from scheduler.writer import Writer

logger = logging.getLogger(__name__)


# ── Default parameter registry (§5.1 — loaded from unified YAML config) ──

def _build_default_registry() -> ParameterRegistry:
    """Build a registry from the single-source-of-truth scheduler.yaml config."""
    from config.loader import build_registry_from_config
    return build_registry_from_config()


# ── Header bar ────────────────────────────────────────────────────────────

class _HeaderBar(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setStyleSheet(f"""
            QWidget {{
                background: {theme.BG_CARD};
                border-bottom: 1px solid {theme.BORDER};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 16, 0)
        layout.setSpacing(16)

        # Logo / title
        logo = QLabel("◈  SysWatch")
        logo.setStyleSheet(
            f"color: {theme.ACCENT}; font-size: 16px; font-weight: 800;"
            " letter-spacing: 1px; border: none;"
        )

        # Live mini stats
        self._lbl_cpu  = self._mini_stat("CPU", "—%")
        self._lbl_mem  = self._mini_stat("MEM", "—%")
        self._lbl_load = self._mini_stat("LOAD", "—")

        # Status badge
        self._badge = QLabel("● LIVE")
        self._badge.setStyleSheet(
            f"color: {theme.ACCENT2}; font-size: 11px; font-weight: 700;"
            f" background: {theme.ACCENT2}22; border: 1px solid {theme.ACCENT2};"
            " border-radius: 10px; padding: 2px 10px;"
        )

        # Buttons
        self._btn_stop = QPushButton("■  Pause")
        self._btn_stop.setFixedWidth(90)
        self._btn_stop.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {theme.TEXT_SEC};
                border: 1px solid {theme.BORDER};
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: {theme.BG_HOVER};
                color: {theme.TEXT_PRI};
            }}
        """)

        layout.addWidget(logo)
        layout.addWidget(self._sep())
        layout.addWidget(self._lbl_cpu)
        layout.addWidget(self._lbl_mem)
        layout.addWidget(self._lbl_load)
        layout.addStretch()
        layout.addWidget(self._badge)
        layout.addWidget(self._btn_stop)

    @staticmethod
    def _mini_stat(label: str, value: str) -> QLabel:
        lbl = QLabel(f"{label}: {value}")
        lbl.setStyleSheet(
            f"color: {theme.TEXT_SEC}; font-size: 12px; font-weight: 600;"
            " border: none;"
        )
        lbl.setMinimumWidth(100)
        return lbl

    @staticmethod
    def _sep() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.VLine)
        f.setStyleSheet(f"color: {theme.BORDER}; border: none; background: {theme.BORDER};")
        f.setFixedWidth(1)
        return f

    def update_stats(self, snap: SystemSnapshot) -> None:
        cpu = snap.cpu_util_pct
        mem = snap.mem_util_pct
        load = snap.load_avg_1

        def _color_pct(v):
            if v is None: return theme.TEXT_SEC
            if v < 60:    return theme.ACCENT2
            if v < 80:    return theme.WARN
            return theme.DANGER

        self._lbl_cpu.setText(f"CPU: {cpu:.0f}%" if cpu is not None else "CPU: —")
        self._lbl_cpu.setStyleSheet(
            f"color: {_color_pct(cpu)}; font-size: 12px; font-weight: 600; border: none;"
        )
        self._lbl_mem.setText(f"MEM: {mem:.0f}%" if mem is not None else "MEM: —")
        self._lbl_mem.setStyleSheet(
            f"color: {_color_pct(mem)}; font-size: 12px; font-weight: 600; border: none;"
        )
        self._lbl_load.setText(f"LOAD: {load:.2f}" if load is not None else "LOAD: —")
        self._lbl_load.setStyleSheet(
            f"color: {theme.TEXT_SEC}; font-size: 12px; font-weight: 600; border: none;"
        )

    def set_paused(self, paused: bool) -> None:
        if paused:
            self._badge.setText("⏸  PAUSED")
            self._badge.setStyleSheet(
                f"color: {theme.WARN}; font-size: 11px; font-weight: 700;"
                f" background: {theme.WARN}22; border: 1px solid {theme.WARN};"
                " border-radius: 10px; padding: 2px 10px;"
            )
            self._btn_stop.setText("▶  Resume")
        else:
            self._badge.setText("● LIVE")
            self._badge.setStyleSheet(
                f"color: {theme.ACCENT2}; font-size: 11px; font-weight: 700;"
                f" background: {theme.ACCENT2}22; border: 1px solid {theme.ACCENT2};"
                " border-radius: 10px; padding: 2px 10px;"
            )
            self._btn_stop.setText("■  Pause")

    @property
    def btn_stop(self) -> QPushButton:
        return self._btn_stop


# ── Main window ───────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(
        self,
        registry: ParameterRegistry,
        controller: SchedulerController | None = None,
        interval_ms: int = 1000,
    ) -> None:
        super().__init__()
        self._paused = False
        self._tick = 0

        self.setWindowTitle("SysWatch — Linux Performance Monitor")
        self.setMinimumSize(1100, 720)
        self.resize(1280, 820)

        # Apply global stylesheet
        self.setStyleSheet(theme.STYLESHEET)

        # ── Root layout ───────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        self._header = _HeaderBar()
        self._header.btn_stop.clicked.connect(self._toggle_pause)
        root.addWidget(self._header)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        root.addWidget(self._tabs, 1)

        # Panels
        self._overview   = OverviewPanel()
        self._processes  = ProcessPanel()
        self._memory     = MemoryPanel()
        self._scheduler  = SchedulerPanel(registry=registry, controller=controller)

        self._tabs.addTab(self._overview,  "  📊  Overview  ")
        self._tabs.addTab(self._processes, "  🔧  Processes  ")
        self._tabs.addTab(self._memory,    "  🧠  Memory  ")
        self._tabs.addTab(self._scheduler, "  ⚙️  Scheduler  ")

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status_lbl = QLabel("Waiting for first snapshot…")
        self._status_lbl.setStyleSheet(f"color: {theme.TEXT_SEC}; font-size: 11px;")
        self._status.addWidget(self._status_lbl)
        self._source_lbl = QLabel()
        self._source_lbl.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 11px;")
        self._status.addPermanentWidget(self._source_lbl)

        # ── Worker ────────────────────────────────────────────────────────
        sched_keys = tuple(p.path for p in registry.get_all())
        monitor = Monitor(default_sources(sched_param_keys=sched_keys))
        self._worker = MonitorWorker(monitor, interval_ms=interval_ms)
        self._worker.snapshot_ready.connect(self._on_snapshot)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

    # ── Slots ─────────────────────────────────────────────────────────────
    def _on_snapshot(self, snap: SystemSnapshot) -> None:
        if self._paused:
            return
        self._tick += 1

        # Update all panels (only the visible tab updates processes for perf)
        self._header.update_stats(snap)
        self._overview.update_snapshot(snap)
        self._memory.update_snapshot(snap)
        self._scheduler.update_snapshot(snap)

        # Process panel is heavy — only refresh when tab is visible
        if self._tabs.currentWidget() is self._processes:
            self._processes.update_snapshot(snap)

        ts = snap.timestamp.astimezone().strftime("%H:%M:%S")
        self._status_lbl.setText(f"Last update: {ts}  •  tick #{self._tick}")
        self._source_lbl.setText(
            f"Sources: {', '.join(snap.available_sources)}"
        )

    def _on_error(self, msg: str) -> None:
        self._status_lbl.setText(f"⚠  {msg}")
        self._status_lbl.setStyleSheet(f"color: {theme.WARN}; font-size: 11px;")

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        self._header.set_paused(self._paused)

    # ── Cleanup ───────────────────────────────────────────────────────────
    def closeEvent(self, event) -> None:  # noqa: N802
        self._worker.stop()
        self._worker.wait(3000)
        super().closeEvent(event)


# ── Public entry point ────────────────────────────────────────────────────

def launch_gui(
    registry: ParameterRegistry | None = None,
    controller: SchedulerController | None = None,
    interval_ms: int = 1000,
) -> None:
    """Start the SysWatch GUI. Blocks until the window is closed."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("SysWatch")
    app.setApplicationDisplayName("SysWatch — Linux Performance Monitor")

    # Force dark palette at OS level too
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor(theme.BG_DEEP))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor(theme.TEXT_PRI))
    palette.setColor(QPalette.ColorRole.Base,            QColor(theme.BG_CARD))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(theme.BG_DEEP))
    palette.setColor(QPalette.ColorRole.Text,            QColor(theme.TEXT_PRI))
    palette.setColor(QPalette.ColorRole.Button,          QColor(theme.BG_HOVER))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor(theme.TEXT_PRI))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor(theme.ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    if registry is None:
        registry = _build_default_registry()

    win = MainWindow(registry=registry, controller=controller, interval_ms=interval_ms)
    win.show()

    sys.exit(app.exec())
