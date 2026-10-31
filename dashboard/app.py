"""
dashboard/app.py — Main application window (full MLOps platform).

Panel inventory
---------------
  MLOps Overview     ← new home page with KPIs and quick-actions
  New Training       ← experiment config + launch
  Live Training      ← real-time metrics from LiveMetricsCallback
  Hyperparameters    ← PPO/SAC tuning
  Scheduler Params   ← sysctl parameter editor
  Reward Config      ← reward component weights
  Benchmarks         ← placeholder (future integration)
  Checkpoints        ← real .zip scanner with evaluate/resume/delete
  Experiment History ← SQLite benchmark + config audit
  Evaluation         ← load checkpoint → run eval episodes
  System Monitor     ← CPU/mem gauges + sparklines
  Processes          ← per-process breakdown
  Memory             ← memory detail
  Safety Panel       ← applied-config audit trail + frequency chart
  Logs               ← live Python log stream
  Settings           ← persisted JSON settings
"""

from __future__ import annotations

import sys
import logging
from datetime import datetime, timezone

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QSizePolicy, QStatusBar, QStackedWidget,
    QVBoxLayout, QWidget, QListWidget, QListWidgetItem, QSplitter, QButtonGroup,
)

from dashboard import theme
from dashboard.panels.mlops_overview      import MLOpsOverviewPanel
from dashboard.panels.new_training        import NewTrainingPanel
from dashboard.panels.live_training       import LiveTrainingPanel
from dashboard.panels.hyperparameters     import HyperparametersPanel
from dashboard.panels.reward_config       import RewardConfigPanel
from dashboard.panels.checkpoints         import CheckpointsPanel
from dashboard.panels.model_benchmark     import ModelBenchmarkPanel
from dashboard.panels.experiment_history  import ExperimentHistoryPanel
from dashboard.panels.evaluation          import EvaluationPanel
from dashboard.panels.safety_panel        import SafetyPanel
from dashboard.panels.log_viewer          import LogViewerPanel
from dashboard.panels.settings_panel      import SettingsPanel, load_settings, save_settings
from dashboard.panels.overview            import OverviewPanel
from dashboard.panels.processes           import ProcessPanel
from dashboard.panels.memory              import MemoryPanel
from dashboard.panels.scheduler           import SchedulerPanel
from dashboard.panels.autotuner_panel       import AutoTunerPanel
from dashboard.panels.placeholders        import PlaceholderPanel
from dashboard.worker                     import MonitorWorker
from monitor.collector                    import Monitor, default_sources
from monitor.types                        import SystemSnapshot
from scheduler.controller                 import SchedulerController
from scheduler.profile                    import ProfileStore
from scheduler.registry                   import ParameterRegistry
from scheduler.rollback                   import RollbackStack
from scheduler.validator                  import Validator
from scheduler.writer                     import Writer

logger = logging.getLogger(__name__)


def _build_default_registry() -> ParameterRegistry:
    from config.loader import build_registry_from_config
    return build_registry_from_config()


# ── Sidebar section label (non-selectable) ───────────────────────────────────

def _sidebar_section(text: str) -> QListWidgetItem:
    item = QListWidgetItem(f"  {text}")
    item.setFlags(Qt.ItemFlag.NoItemFlags)
    item.setFont(QFont("Inter", 10, QFont.Weight.ExtraBold))
    item.setForeground(QColor(theme.TEXT_DIM))
    return item


# ── Header bar ───────────────────────────────────────────────────────────────

class _HeaderBar(QWidget):
    theme_requested = pyqtSignal(str)

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

        logo = QLabel("◈  STUN-Project  MLOps")
        logo.setStyleSheet(
            f"color: {theme.ACCENT}; font-size: 15px; font-weight: 800;"
            " letter-spacing: 1px; border: none;"
        )

        self._lbl_cpu  = self._mini_stat("CPU",  "—%")
        self._lbl_mem  = self._mini_stat("MEM",  "—%")
        self._lbl_load = self._mini_stat("LOAD", "—")

        self._badge = QLabel("● LIVE")
        self._badge.setStyleSheet(
            f"color: {theme.ACCENT2}; font-size: 11px; font-weight: 700;"
            f" background: {theme.ACCENT2}22; border: 1px solid {theme.ACCENT2};"
            " border-radius: 10px; padding: 2px 10px;"
        )

        self._btn_pause = QPushButton("⏸  Pause Monitor")
        self._btn_pause.setFixedWidth(130)
        self._btn_pause.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {theme.TEXT_SEC};
                border: 1px solid {theme.BORDER}; border-radius: 6px;
                padding: 5px 12px; font-size: 12px;
            }}
            QPushButton:hover {{ background: {theme.BG_HOVER}; color: {theme.TEXT_PRI}; }}
        """)

        layout.addWidget(logo)
        layout.addWidget(self._sep())
        layout.addWidget(self._lbl_cpu)
        layout.addWidget(self._lbl_mem)
        layout.addWidget(self._lbl_load)
        layout.addStretch()
        self.btn_light = QPushButton("☀ White")
        self.btn_dark = QPushButton("☾ Black")
        self._theme_buttons = QButtonGroup(self)
        for button_id, (button, name) in enumerate(((self.btn_light, "light"), (self.btn_dark, "dark"))):
            button.setCheckable(True)
            button.setChecked(theme.current_theme == name)
            button.setObjectName(f"theme_{name}")
            button.setAccessibleName(f"Switch to {name} theme")
            button.setToolTip(f"Use the {'white' if name == 'light' else 'black'} dashboard theme")
            button.setFixedWidth(88)
            button.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {theme.TEXT_SEC};
                    border: 1px solid {theme.BORDER}; border-radius: 7px; padding: 6px 10px; }}
                QPushButton:hover {{ background: {theme.BG_HOVER}; color: {theme.TEXT_PRI}; }}
                QPushButton:checked {{ background: {theme.ACCENT}; color: #fff;
                    border-color: {theme.ACCENT}; }}
            """)
            self._theme_buttons.addButton(button, button_id)
            layout.addWidget(button)
        self._theme_buttons.idClicked.connect(
            lambda button_id: self.theme_requested.emit("light" if button_id == 0 else "dark"))
        layout.addWidget(self._badge)
        layout.addWidget(self._btn_pause)

    @staticmethod
    def _mini_stat(label: str, value: str) -> QLabel:
        lbl = QLabel(f"{label}: {value}")
        lbl.setStyleSheet(f"color: {theme.TEXT_SEC}; font-size: 12px; font-weight: 600; border: none;")
        lbl.setMinimumWidth(90)
        return lbl

    @staticmethod
    def _sep() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.VLine)
        f.setStyleSheet(f"color: {theme.BORDER}; border: none; background: {theme.BORDER};")
        f.setFixedWidth(1)
        return f

    def update_stats(self, snap: SystemSnapshot) -> None:
        def _color(v):
            if v is None:   return theme.TEXT_SEC
            if v < 60:      return theme.ACCENT2
            if v < 80:      return theme.WARN
            return theme.DANGER

        cpu  = snap.cpu_util_pct
        mem  = snap.mem_util_pct
        load = snap.load_avg_1

        self._lbl_cpu.setText(f"CPU: {cpu:.0f}%" if cpu is not None else "CPU: —")
        self._lbl_cpu.setStyleSheet(f"color: {_color(cpu)}; font-size: 12px; font-weight: 600; border: none;")
        self._lbl_mem.setText(f"MEM: {mem:.0f}%" if mem is not None else "MEM: —")
        self._lbl_mem.setStyleSheet(f"color: {_color(mem)}; font-size: 12px; font-weight: 600; border: none;")
        self._lbl_load.setText(f"LOAD: {load:.2f}" if load is not None else "LOAD: —")
        self._lbl_load.setStyleSheet(f"color: {theme.TEXT_SEC}; font-size: 12px; font-weight: 600; border: none;")

    def set_paused(self, paused: bool) -> None:
        if paused:
            self._badge.setText("⏸  PAUSED")
            self._badge.setStyleSheet(
                f"color: {theme.WARN}; background: {theme.WARN}22;"
                f" border: 1px solid {theme.WARN}; border-radius: 10px; padding: 2px 10px;"
                " font-weight: 700; font-size: 11px;"
            )
            self._btn_pause.setText("▶  Resume Monitor")
        else:
            self._badge.setText("● LIVE")
            self._badge.setStyleSheet(
                f"color: {theme.ACCENT2}; background: {theme.ACCENT2}22;"
                f" border: 1px solid {theme.ACCENT2}; border-radius: 10px; padding: 2px 10px;"
                " font-weight: 700; font-size: 11px;"
            )
            self._btn_pause.setText("⏸  Pause Monitor")

    @property
    def btn_pause(self) -> QPushButton:
        return self._btn_pause


# ── Main Window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(
        self,
        registry: ParameterRegistry,
        controller: SchedulerController | None = None,
        interval_ms: int = 1000,
    ) -> None:
        super().__init__()
        preference = load_settings().get("theme", "dark")
        theme.set_theme(preference if preference in ("light", "dark") else "dark")
        self._paused = False
        self._tick   = 0

        self.setWindowTitle("STUN-Project — RL Scheduler MLOps Platform")
        self.setMinimumSize(1280, 820)
        self.setStyleSheet(theme.STYLESHEET)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        self._header = _HeaderBar()
        self._header.btn_pause.clicked.connect(self._toggle_pause)
        self._header.theme_requested.connect(self._set_theme)
        root.addWidget(self._header)

        # Splitter (sidebar + content)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(self.splitter, 1)

        # ── Sidebar ───────────────────────────────────────────────────────
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(224)
        self.sidebar.setStyleSheet(f"""
            QListWidget {{
                background-color: {theme.BG_DEEP};
                border-right: 1px solid {theme.BORDER};
                outline: none;
                padding-top: 6px;
            }}
            QListWidget::item {{
                color: {theme.TEXT_SEC};
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 600;
                border-left: 3px solid transparent;
                border-radius: 0;
            }}
            QListWidget::item:hover {{
                background-color: {theme.BG_CARD};
                color: {theme.TEXT_PRI};
            }}
            QListWidget::item:selected {{
                background-color: {theme.BG_CARD};
                color: {theme.ACCENT};
                border-left: 3px solid {theme.ACCENT};
            }}
        """)
        self.splitter.addWidget(self.sidebar)

        # Content area
        self.stack = QStackedWidget()
        self.splitter.addWidget(self.stack)
        self.splitter.setStretchFactor(1, 1)

        # ── Instantiate all panels ────────────────────────────────────────
        self._p_mlops     = MLOpsOverviewPanel()
        self._p_new_train = NewTrainingPanel()
        self._p_live      = LiveTrainingPanel()
        self._p_hyper     = HyperparametersPanel()
        self._p_reward    = RewardConfigPanel()
        self._p_scheduler = SchedulerPanel(registry=registry, controller=controller)
        self._p_autotuner = AutoTunerPanel()
        self._p_benchmarks = PlaceholderPanel("Benchmark Runner")
        self._p_checkpoints  = CheckpointsPanel()
        self._p_model_bm   = ModelBenchmarkPanel()
        self._p_history   = ExperimentHistoryPanel()
        self._p_eval      = EvaluationPanel()
        self._p_sys_ov    = OverviewPanel()
        self._p_procs     = ProcessPanel()
        self._p_mem       = MemoryPanel()
        self._p_safety    = SafetyPanel()
        self._p_logs      = LogViewerPanel()
        self._p_settings  = SettingsPanel()

        # ── Sidebar groups + pages map ────────────────────────────────────
        # Format: (sidebar_label, panel_widget)
        # Section headers are tuples of (label, None)
        _layout = [
            # section header
            ("── EXPERIMENTS", None),
            ("Overview",            self._p_mlops),
            ("New Training",        self._p_new_train),
            ("Live Training",       self._p_live),
            ("Hyperparameters",     self._p_hyper),
            ("Reward Config",       self._p_reward),
            # section header
            ("── SCHEDULER", None),
            ("Scheduler Params",    self._p_scheduler),
            ("Auto-Tuner & Sweep",  self._p_autotuner),
            ("Checkpoints",         self._p_checkpoints),
            ("Model Benchmark",     self._p_model_bm),
            ("Experiment History",  self._p_history),
            ("Evaluation",          self._p_eval),
            # section header
            ("── SYSTEM", None),
            ("System Monitor",      self._p_sys_ov),
            ("Processes",           self._p_procs),
            ("Memory",              self._p_mem),
            # section header
            ("── PLATFORM", None),
            ("Safety Panel",        self._p_safety),
            ("Logs",                self._p_logs),
            ("Settings",            self._p_settings),
        ]

        # Build sidebar items and stack
        # Keep a mapping from sidebar row → stack index
        self._row_to_stack: dict[int, int] = {}
        self._name_to_row:  dict[str, int] = {}
        stack_idx = 0
        for sidebar_row, (label, widget) in enumerate(_layout):
            if widget is None:
                # Section header — non-selectable
                item = _sidebar_section(label.lstrip("─ "))
                self.sidebar.addItem(item)
            else:
                item = QListWidgetItem(f"  {label}")
                self.sidebar.addItem(item)
                self.stack.addWidget(widget)
                self._row_to_stack[sidebar_row] = stack_idx
                self._name_to_row[label.strip()] = sidebar_row
                stack_idx += 1

        self.sidebar.currentRowChanged.connect(self._on_sidebar_changed)

        # ── Wire inter-panel signals ──────────────────────────────────────
        # MLOps quick-actions → navigate
        self._p_mlops.navigate_requested.connect(self._navigate_to)

        # NewTraining launch → configure LiveTraining + navigate
        self._p_new_train.launch_requested.connect(self._on_launch_requested)

        # Checkpoints → Evaluation panel
        self._p_checkpoints.evaluate_requested.connect(self._on_evaluate_from_checkpoint)
        self._p_checkpoints.resume_requested.connect(self._on_resume_from_checkpoint)

        # Settings changes → propagate paths
        self._p_settings.settings_changed.connect(self._on_settings_changed)

        # ── Status bar ────────────────────────────────────────────────────
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status_lbl = QLabel("Initialising system monitor…")
        self._status_lbl.setStyleSheet(f"color: {theme.TEXT_SEC}; font-size: 11px;")
        self._status.addWidget(self._status_lbl)

        # ── System monitor worker ─────────────────────────────────────────
        sched_keys = tuple(p.path for p in registry.get_all())
        monitor = Monitor(default_sources(sched_param_keys=sched_keys))
        self._worker = MonitorWorker(monitor, interval_ms=interval_ms)
        self._worker.snapshot_ready.connect(self._on_snapshot)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

        # Navigate to MLOps Overview on startup
        self._navigate_to("Overview")
        self._set_theme(theme.current_theme, persist=False)

    def _set_theme(self, name: str, *, persist: bool = True) -> None:
        theme.apply_to_window(self, name)
        self._header.btn_light.setChecked(name == "light")
        self._header.btn_dark.setChecked(name == "dark")
        self._p_settings.set_theme_preference(name)
        if persist:
            settings = load_settings()
            settings["theme"] = name
            try:
                save_settings(settings)
            except OSError:
                logger.warning("Theme changed but the preference could not be saved", exc_info=True)
                self.statusBar().showMessage("Theme changed; preference could not be saved.", 5000)

    # ── Sidebar navigation ────────────────────────────────────────────────

    def _on_sidebar_changed(self, sidebar_row: int) -> None:
        stack_idx = self._row_to_stack.get(sidebar_row)
        if stack_idx is not None:
            self.stack.setCurrentIndex(stack_idx)

    def _navigate_to(self, page_name: str) -> None:
        """Navigate to a panel by its sidebar label."""
        row = self._name_to_row.get(page_name)
        if row is not None:
            self.sidebar.setCurrentRow(row)

    # ── Cross-panel signal handlers ───────────────────────────────────────

    def _on_launch_requested(self, config) -> None:
        """Apply config to LiveTrainingPanel and navigate to it."""
        self._p_live.apply_config(config)
        self._navigate_to("Live Training")
        self._p_live.start_training()

    def _on_evaluate_from_checkpoint(self, path: str, algo: str) -> None:
        self._p_eval._inp_path.setText(path)
        idx = self._p_eval._cmb_algo.findText(algo)
        if idx >= 0:
            self._p_eval._cmb_algo.setCurrentIndex(idx)
        self._navigate_to("Evaluation")

    def _on_resume_from_checkpoint(self, path: str, algo: str) -> None:
        from dashboard.panels.live_training import TrainingConfig
        cfg = TrainingConfig(
            experiment_name="Resumed Run",
            algorithm=algo,
            timesteps=50_000,
            checkpoint_dir="data/checkpoints",
        )
        self._p_live.apply_config(cfg)
        self._navigate_to("Live Training")

    def _on_settings_changed(self, settings: dict) -> None:
        self._set_theme(settings.get("theme", "dark"), persist=False)
        ckpt_dir = settings.get("checkpoint_dir", "data/checkpoints")
        self._p_checkpoints.set_checkpoint_dir(ckpt_dir)
        from pathlib import Path
        self._p_mlops._ckpt_dir = Path(ckpt_dir)
        logger.info("Settings updated: %s", settings)

    # ── System snapshot handler ───────────────────────────────────────────

    def _on_snapshot(self, snap: SystemSnapshot) -> None:
        if self._paused:
            return
        self._tick += 1

        self._header.update_stats(snap)
        self._p_sys_ov.update_snapshot(snap)
        self._p_mem.update_snapshot(snap)
        self._p_scheduler.update_snapshot(snap)

        if self.stack.currentWidget() is self._p_procs:
            self._p_procs.update_snapshot(snap)

        ts = snap.timestamp.astimezone().strftime("%H:%M:%S")
        self._status_lbl.setText(
            f"System Monitor: Active  •  Last update: {ts}  •  Tick #{self._tick}"
        )

    def _on_error(self, msg: str) -> None:
        self._status_lbl.setText(f"⚠  {msg}")
        self._status_lbl.setStyleSheet(f"color: {theme.WARN}; font-size: 11px;")

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        self._header.set_paused(self._paused)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._worker.stop()
        self._worker.wait(3000)
        super().closeEvent(event)


# ── Entry point ───────────────────────────────────────────────────────────────

def launch_gui(
    registry:    ParameterRegistry | None = None,
    controller:  SchedulerController | None = None,
    interval_ms: int = 1000,
) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("STUN-Project MLOps")

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


if __name__ == "__main__":
    launch_gui()
