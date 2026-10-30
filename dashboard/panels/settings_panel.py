"""
dashboard/panels/settings_panel.py — Settings panel.

Provides controls for:
  - Dashboard refresh interval
  - Checkpoint directory path
  - DB path
  - Monitor polling frequency
  - Theme preference toggle (future)
"""
from __future__ import annotations
import json
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QSpinBox, QVBoxLayout, QWidget,
)
from dashboard import theme

_SETTINGS_FILE = Path("data/dashboard_settings.json")

_DEFAULTS = {
    "checkpoint_dir":      "data/checkpoints",
    "db_path":             "data/experiments.db",
    "monitor_interval_ms": 1000,
    "log_max_lines":       5000,
    "training_timesteps":  50000,
    "training_checkpoint_freq": 5000,
}


def load_settings() -> dict:
    if _SETTINGS_FILE.is_file():
        try:
            return {**_DEFAULTS, **json.loads(_SETTINGS_FILE.read_text())}
        except Exception:
            pass
    return dict(_DEFAULTS)


def save_settings(s: dict) -> None:
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_FILE.write_text(json.dumps(s, indent=2))


class SettingsPanel(QWidget):
    """User-configurable dashboard settings."""

    settings_changed = pyqtSignal(dict)   # emitted whenever settings are saved

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._settings = load_settings()

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(20)

        title = QLabel("Settings")
        title.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {theme.TEXT_PRI}; border: none;")
        root.addWidget(title)

        sub = QLabel("Configuration changes are persisted to data/dashboard_settings.json.")
        sub.setStyleSheet(f"color: {theme.TEXT_SEC}; font-size: 13px; border: none;")
        root.addWidget(sub)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_w = QWidget()
        scroll_w.setStyleSheet("background: transparent;")
        scroll_lay = QVBoxLayout(scroll_w)
        scroll_lay.setSpacing(16)

        # ── Paths ──────────────────────────────────────────────────────────
        paths_grp = QGroupBox("Paths")
        paths_lay = QFormLayout(paths_grp)
        paths_lay.setSpacing(10)

        self._inp_ckpt_dir = self._path_row(
            paths_lay, "Checkpoint Directory:",
            self._settings["checkpoint_dir"], is_dir=True
        )
        self._inp_db = self._path_row(
            paths_lay, "SQLite Database:",
            self._settings["db_path"], is_dir=False
        )
        scroll_lay.addWidget(paths_grp)

        # ── Monitoring ─────────────────────────────────────────────────────
        mon_grp = QGroupBox("System Monitor")
        mon_lay = QFormLayout(mon_grp)
        mon_lay.setSpacing(10)

        self._spin_interval = QSpinBox()
        self._spin_interval.setRange(250, 10000)
        self._spin_interval.setSingleStep(250)
        self._spin_interval.setValue(self._settings["monitor_interval_ms"])
        self._spin_interval.setSuffix(" ms")
        mon_lay.addRow("Poll Interval:", self._spin_interval)

        self._spin_log_lines = QSpinBox()
        self._spin_log_lines.setRange(100, 50000)
        self._spin_log_lines.setValue(self._settings["log_max_lines"])
        mon_lay.addRow("Log Max Lines:", self._spin_log_lines)
        scroll_lay.addWidget(mon_grp)

        # ── Training defaults ──────────────────────────────────────────────
        train_grp = QGroupBox("Training Defaults")
        train_lay = QFormLayout(train_grp)
        train_lay.setSpacing(10)

        self._spin_timesteps = QSpinBox()
        self._spin_timesteps.setRange(1000, 10_000_000)
        self._spin_timesteps.setSingleStep(10000)
        self._spin_timesteps.setValue(self._settings["training_timesteps"])
        train_lay.addRow("Default Total Timesteps:", self._spin_timesteps)

        self._spin_ckpt_freq = QSpinBox()
        self._spin_ckpt_freq.setRange(100, 100_000)
        self._spin_ckpt_freq.setSingleStep(1000)
        self._spin_ckpt_freq.setValue(self._settings["training_checkpoint_freq"])
        train_lay.addRow("Checkpoint Frequency:", self._spin_ckpt_freq)
        scroll_lay.addWidget(train_grp)

        scroll_lay.addStretch()
        scroll.setWidget(scroll_w)
        root.addWidget(scroll, 1)

        # ── Buttons ─────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_reset = QPushButton("↺  Reset Defaults")
        self._btn_reset.clicked.connect(self._reset)
        self._btn_save = QPushButton("✓  Save Settings")
        self._btn_save.setObjectName("btn_success")
        self._btn_save.clicked.connect(self._save)
        btn_row.addWidget(self._btn_reset)
        btn_row.addWidget(self._btn_save)
        root.addLayout(btn_row)

        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet(f"color: {theme.ACCENT2}; font-size: 12px; border: none;")
        root.addWidget(self._lbl_status)

    # ── Helpers ────────────────────────────────────────────────────────────

    def _path_row(self, form_lay: QFormLayout, label: str,
                  default: str, is_dir: bool) -> QLineEdit:
        row_w = QWidget()
        row_l = QHBoxLayout(row_w)
        row_l.setContentsMargins(0, 0, 0, 0)
        inp = QLineEdit(default)
        row_l.addWidget(inp, 1)
        btn = QPushButton("Browse…")
        btn.setFixedWidth(90)
        if is_dir:
            btn.clicked.connect(lambda: inp.setText(
                QFileDialog.getExistingDirectory(self, label, inp.text()) or inp.text()
            ))
        else:
            btn.clicked.connect(lambda: inp.setText(
                QFileDialog.getSaveFileName(self, label, inp.text(), "DB files (*.db)")[0] or inp.text()
            ))
        row_l.addWidget(btn)
        form_lay.addRow(label, row_w)
        return inp

    def _collect(self) -> dict:
        return {
            "checkpoint_dir":            self._inp_ckpt_dir.text().strip(),
            "db_path":                   self._inp_db.text().strip(),
            "monitor_interval_ms":       self._spin_interval.value(),
            "log_max_lines":             self._spin_log_lines.value(),
            "training_timesteps":        self._spin_timesteps.value(),
            "training_checkpoint_freq":  self._spin_ckpt_freq.value(),
        }

    def _save(self) -> None:
        s = self._collect()
        save_settings(s)
        self._settings = s
        self._lbl_status.setText("✓  Settings saved successfully.")
        self.settings_changed.emit(s)

    def _reset(self) -> None:
        s = dict(_DEFAULTS)
        self._inp_ckpt_dir.setText(s["checkpoint_dir"])
        self._inp_db.setText(s["db_path"])
        self._spin_interval.setValue(s["monitor_interval_ms"])
        self._spin_log_lines.setValue(s["log_max_lines"])
        self._spin_timesteps.setValue(s["training_timesteps"])
        self._spin_ckpt_freq.setValue(s["training_checkpoint_freq"])
        self._lbl_status.setText("Defaults restored — click Save to apply.")

    def get_settings(self) -> dict:
        return dict(self._settings)
