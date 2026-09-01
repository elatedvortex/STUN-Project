"""
dashboard/panels/scheduler.py — Scheduler Tuning tab (v2).

Reads /proc/sys directly — no root needed for reads.
Writes via SchedulerController when root is available.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import pyqtgraph as pg
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDoubleSpinBox, QFormLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSlider, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from dashboard import theme
from dashboard.widgets import AlertBanner, SectionHeader, SparklineChart
from monitor.types import SystemSnapshot
from scheduler.controller import SchedulerController
from scheduler.registry import ParameterRegistry
from scheduler.types import ParameterMeta

logger = logging.getLogger(__name__)

_HEADERS = ["Parameter", "Current Value", "Min", "Max", "Description"]
_COL_NAME    = 0
_COL_CURRENT = 1
_COL_MIN     = 2
_COL_MAX     = 3
_COL_DESC    = 4

# Read a sysctl value directly from /proc/sys (no root needed)
def _read_sysctl(path_dotted: str) -> Optional[str]:
    fspath = Path("/proc/sys") / path_dotted.replace(".", "/")
    try:
        return fspath.read_text().strip()
    except OSError:
        return None

# Write a sysctl value directly (requires root)
def _write_sysctl(path_dotted: str, value: str) -> bool:
    fspath = Path("/proc/sys") / path_dotted.replace(".", "/")
    try:
        fspath.write_text(value + "\n")
        return True
    except OSError as e:
        logger.error("sysctl write failed %s: %s", path_dotted, e)
        return False


class SchedulerPanel(QWidget):
    def __init__(
        self,
        registry: ParameterRegistry,
        controller: Optional[SchedulerController] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._registry   = registry
        self._controller = controller
        self._selected_meta: Optional[ParameterMeta] = None
        self._live_values: Dict[str, str] = {}   # path → raw string value
        self._is_root = (os.geteuid() == 0)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # ── Banner ────────────────────────────────────────────────────────
        if not self._is_root:
            root.addWidget(AlertBanner(
                "Running as non-root — reads are live, but writes are disabled. "
                "Restart with sudo to enable Apply.",
                level="warn",
            ))
        else:
            root.addWidget(AlertBanner(
                "Running as root — writes are ENABLED. Changes take effect immediately.",
                level="warn",
            ))

        root.addWidget(SectionHeader("Kernel Scheduler Tunables  (/proc/sys/kernel/sched_*)"))

        # ── Main splitter ─────────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── LEFT: parameter table ──────────────────────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(8)

        self._table = QTableWidget(0, len(_HEADERS))
        self._table.setHorizontalHeaderLabels(_HEADERS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(_COL_NAME, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(_COL_DESC, QHeaderView.ResizeMode.Stretch)
        self._table.setShowGrid(False)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background: {theme.BG_CARD};
                alternate-background-color: {theme.BG_DEEP};
                border-radius: 8px; font-size: 12px;
            }}
            QTableWidget::item {{ padding: 6px 10px; }}
            QTableWidget::item:selected {{
                background: #1f6feb33; color: {theme.ACCENT};
            }}
        """)
        self._table.itemSelectionChanged.connect(self._on_row_selected)
        left_layout.addWidget(self._table)

        # Preset buttons row
        preset_row = QHBoxLayout()
        _pl = QLabel("Quick Presets:")
        _pl.setStyleSheet(f"color:{theme.TEXT_SEC};font-size:11px;")
        preset_row.addWidget(_pl)
        for label, tip in [
            ("⚡ Low-Latency RT", "Maximise RT headroom"),
            ("🔋 Power Save", "Reduce scheduler overhead"),
            ("⚖ Balanced", "Restore safe defaults"),
        ]:
            btn = QPushButton(label)
            btn.setToolTip(tip)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda _, l=label: self._apply_preset(l))
            preset_row.addWidget(btn)
        preset_row.addStretch()
        left_layout.addLayout(preset_row)

        splitter.addWidget(left)

        # ── RIGHT: editor + history chart ─────────────────────────────────
        right = QWidget()
        right.setFixedWidth(310)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # Detail card
        detail = QGroupBox("Selected Parameter")
        detail.setStyleSheet(f"QGroupBox {{ background:{theme.BG_CARD}; border:1px solid {theme.BORDER}; border-radius:8px; margin-top:12px; padding:12px; }} QGroupBox::title {{ subcontrol-origin:margin; left:12px; top:-8px; color:{theme.TEXT_SEC}; font-size:10px; }}")
        df = QFormLayout(detail)
        df.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        df.setSpacing(6)

        self._lbl_name    = QLabel("—")
        self._lbl_name.setStyleSheet(f"color:{theme.ACCENT};font-weight:700;font-size:13px;")
        self._lbl_current = QLabel("—")
        self._lbl_current.setStyleSheet(f"color:{theme.ACCENT2};font-weight:700;font-size:18px;")
        self._lbl_desc    = QLabel("—")
        self._lbl_desc.setWordWrap(True)
        self._lbl_desc.setStyleSheet(f"color:{theme.TEXT_SEC};font-size:11px;")
        self._lbl_range   = QLabel("—")
        self._lbl_range.setStyleSheet(f"color:{theme.TEXT_DIM};font-size:11px;")

        df.addRow("Name:", self._lbl_name)
        df.addRow("Current:", self._lbl_current)
        df.addRow("Range:", self._lbl_range)
        df.addRow("About:", self._lbl_desc)
        right_layout.addWidget(detail)

        # Editor card
        editor = QGroupBox("Edit Value")
        editor.setStyleSheet(detail.styleSheet())
        el = QVBoxLayout(editor)
        el.setSpacing(8)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 1000)
        self._spinbox = QDoubleSpinBox()
        self._spinbox.setDecimals(0)
        self._spinbox.setMinimumWidth(100)
        self._spinbox.setStyleSheet(f"font-size:14px;font-weight:600;color:{theme.ACCENT};")

        val_row = QHBoxLayout()
        val_row.addWidget(self._slider, 1)
        val_row.addWidget(self._spinbox)
        el.addLayout(val_row)

        btn_row = QHBoxLayout()
        self._btn_apply = QPushButton("✔  Apply")
        self._btn_apply.setObjectName("btn_success")
        self._btn_apply.setEnabled(self._is_root)
        self._btn_rollback = QPushButton("↩  Rollback")
        self._btn_rollback.setObjectName("btn_warn")
        self._btn_reset = QPushButton("⟳  Reset")
        btn_row.addWidget(self._btn_apply)
        btn_row.addWidget(self._btn_rollback)
        btn_row.addWidget(self._btn_reset)
        el.addLayout(btn_row)
        right_layout.addWidget(editor)

        # Profile card
        prof = QGroupBox("Profiles")
        prof.setStyleSheet(detail.styleSheet())
        pl = QVBoxLayout(prof)
        pl.setSpacing(6)
        self._profile_name = QLineEdit()
        self._profile_name.setPlaceholderText("Profile name…")
        self._btn_save_profile = QPushButton("💾  Save Current as Profile")
        self._profile_combo = QComboBox()
        self._btn_load_profile = QPushButton("▶  Load Profile")
        pl.addWidget(self._profile_name)
        pl.addWidget(self._btn_save_profile)
        _sl = QLabel("Saved profiles:")
        _sl.setStyleSheet(f"color:{theme.TEXT_SEC};font-size:11px;")
        pl.addWidget(_sl)
        pl.addWidget(self._profile_combo)
        pl.addWidget(self._btn_load_profile)
        right_layout.addWidget(prof)
        right_layout.addStretch()

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        # ── Wire up ───────────────────────────────────────────────────────
        self._slider.valueChanged.connect(self._slider_moved)
        self._spinbox.valueChanged.connect(self._spinbox_moved)
        self._btn_apply.clicked.connect(self._apply)
        self._btn_rollback.clicked.connect(self._rollback)
        self._btn_reset.clicked.connect(self._reset_to_live)
        self._btn_save_profile.clicked.connect(self._save_profile)
        self._btn_load_profile.clicked.connect(self._load_profile)

        # ── Initial populate ──────────────────────────────────────────────
        self._refresh_live_values()
        self._populate_table()

        # Auto-refresh live values every 2s independent of snapshot
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_live_values)
        self._timer.start(2000)

    # ── Direct /proc/sys read ─────────────────────────────────────────────
    def _refresh_live_values(self) -> None:
        changed = False
        for meta in self._registry.get_all():
            val = _read_sysctl(meta.path)
            if val is not None and val != self._live_values.get(meta.path):
                self._live_values[meta.path] = val
                changed = True
        if changed:
            self._update_table_values()
            if self._selected_meta:
                self._update_detail(self._selected_meta)

    def _update_table_values(self) -> None:
        params = self._registry.get_all()
        for row, meta in enumerate(params):
            val = self._live_values.get(meta.path, "—")
            item = self._table.item(row, _COL_CURRENT)
            if item:
                item.setText(val)
                # Colour the value cell based on proximity to bounds
                try:
                    v = float(val)
                    if meta.max_value and v >= float(meta.max_value) * 0.9:
                        item.setForeground(QColor(theme.DANGER))
                    elif meta.min_value is not None and v <= float(meta.min_value):
                        item.setForeground(QColor(theme.TEXT_SEC))
                    else:
                        item.setForeground(QColor(theme.ACCENT2))
                except (ValueError, TypeError):
                    item.setForeground(QColor(theme.TEXT_SEC))

    # ── Table ─────────────────────────────────────────────────────────────
    def _populate_table(self) -> None:
        params = self._registry.get_all()
        self._table.setRowCount(len(params))
        for row, meta in enumerate(params):
            self._table.setItem(row, _COL_NAME, QTableWidgetItem(meta.name))
            val = self._live_values.get(meta.path, "—")
            cur = QTableWidgetItem(val)
            cur.setForeground(QColor(theme.ACCENT2))
            cur.setFont(QFont("Inter", 11, QFont.Weight.Bold))
            self._table.setItem(row, _COL_CURRENT, cur)
            self._table.setItem(row, _COL_MIN, QTableWidgetItem(str(meta.min_value)))
            self._table.setItem(row, _COL_MAX, QTableWidgetItem(str(meta.max_value)))
            self._table.setItem(row, _COL_DESC, QTableWidgetItem(meta.description or ""))
        self._table.resizeRowsToContents()

    def _on_row_selected(self) -> None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        params = self._registry.get_all()
        row = rows[0].row()
        if row >= len(params):
            return
        self._selected_meta = params[row]
        self._update_detail(self._selected_meta)

    def _update_detail(self, meta: ParameterMeta) -> None:
        val_str = self._live_values.get(meta.path, "—")
        self._lbl_name.setText(meta.name)
        self._lbl_current.setText(val_str)
        self._lbl_range.setText(f"{meta.min_value}  →  {meta.max_value}")
        self._lbl_desc.setText(meta.description or "No description.")

        # Sync editor
        try:
            val = float(val_str)
        except ValueError:
            val = float(meta.min_value or 0)

        self._slider.blockSignals(True)
        self._spinbox.blockSignals(True)
        lo = float(meta.min_value or 0)
        hi = float(meta.max_value or 1)
        self._spinbox.setRange(lo, hi)
        self._spinbox.setValue(val)
        self._slider.setValue(self._to_slider(val, lo, hi))
        self._slider.blockSignals(False)
        self._spinbox.blockSignals(False)

    # ── Snapshot hook (kept for compatibility; direct timer used instead) ─
    def update_snapshot(self, snap: SystemSnapshot) -> None:
        pass

    # ── Slider / spinbox sync ─────────────────────────────────────────────
    def _to_slider(self, value: float, lo: float, hi: float) -> int:
        if hi == lo:
            return 0
        return int(max(0, min(1000, (value - lo) / (hi - lo) * 1000)))

    def _from_slider(self, sv: int, lo: float, hi: float) -> float:
        return lo + (hi - lo) * sv / 1000

    def _slider_moved(self, sv: int) -> None:
        if not self._selected_meta:
            return
        lo = float(self._selected_meta.min_value or 0)
        hi = float(self._selected_meta.max_value or 1)
        self._spinbox.blockSignals(True)
        self._spinbox.setValue(self._from_slider(sv, lo, hi))
        self._spinbox.blockSignals(False)

    def _spinbox_moved(self, v: float) -> None:
        if not self._selected_meta:
            return
        lo = float(self._selected_meta.min_value or 0)
        hi = float(self._selected_meta.max_value or 1)
        self._slider.blockSignals(True)
        self._slider.setValue(self._to_slider(v, lo, hi))
        self._slider.blockSignals(False)

    # ── Actions ───────────────────────────────────────────────────────────
    def _apply(self) -> None:
        if not self._selected_meta:
            return
        value = int(self._spinbox.value())
        path  = self._selected_meta.path

        if self._controller:
            try:
                self._controller.apply_parameters({self._selected_meta.name: value})
            except Exception as exc:
                QMessageBox.critical(self, "Controller Error", str(exc))
                return
        else:
            # Direct write (root required)
            ok = _write_sysctl(path, str(value))
            if not ok:
                QMessageBox.critical(self, "Write Failed",
                    f"Could not write {path}.\nAre you running as root?")
                return

        self._live_values[path] = str(value)
        self._update_table_values()
        self._lbl_current.setText(str(value))
        self._show_status(f"✔  {self._selected_meta.name} = {value}")

    def _rollback(self) -> None:
        if self._controller:
            try:
                self._controller.rollback()
                QMessageBox.information(self, "Rolled back", "Last change rolled back.")
                self._refresh_live_values()
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))
        else:
            QMessageBox.information(self, "No controller",
                "Rollback requires --with-scheduler mode (root).")

    def _reset_to_live(self) -> None:
        """Sync spinbox/slider back to the live on-disk value."""
        if self._selected_meta:
            self._refresh_live_values()
            self._update_detail(self._selected_meta)

    def _save_profile(self) -> None:
        name = self._profile_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Name required", "Enter a profile name.")
            return
        if self._controller:
            try:
                self._controller.profile_store.save_profile(name, {
                    m.name: int(self._live_values.get(m.path, 0))
                    for m in self._registry.get_all()
                    if self._live_values.get(m.path)
                })
                self._profile_combo.addItem(name)
                self._show_status(f"💾  Profile '{name}' saved.")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))
        else:
            QMessageBox.information(self, "No controller",
                "Profile save requires --with-scheduler mode.")

    def _load_profile(self) -> None:
        if not self._controller:
            return
        name = self._profile_combo.currentText()
        if not name:
            return
        try:
            self._controller.apply_profile(name)
            self._refresh_live_values()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _apply_preset(self, label: str) -> None:
        """Apply a known-safe preset directly."""
        presets: dict[str, dict[str, int]] = {
            "⚡ Low-Latency RT": {
                "kernel.sched_rt_runtime_us":  950_000,
                "kernel.sched_rt_period_us":   1_000_000,
                "kernel.sched_rr_timeslice_ms": 10,
            },
            "🔋 Power Save": {
                "kernel.sched_rt_runtime_us":  750_000,
                "kernel.sched_rr_timeslice_ms": 200,
                "kernel.sched_autogroup_enabled": 1,
            },
            "⚖ Balanced": {
                "kernel.sched_rt_runtime_us":  950_000,
                "kernel.sched_rt_period_us":   1_000_000,
                "kernel.sched_rr_timeslice_ms": 100,
                "kernel.sched_autogroup_enabled": 1,
                "kernel.sched_util_clamp_max": 1024,
                "kernel.sched_util_clamp_min": 1024,
            },
        }
        values = presets.get(label, {})
        if not values:
            return
        if not self._is_root:
            QMessageBox.warning(self, "Root required",
                "Presets write to sysctl — restart with sudo.")
            return
        errors = []
        for path, val in values.items():
            if not _write_sysctl(path, str(val)):
                errors.append(path)
        self._refresh_live_values()
        if errors:
            QMessageBox.warning(self, "Partial apply",
                f"Could not write:\n" + "\n".join(errors))
        else:
            self._show_status(f"✔  Preset '{label}' applied.")

    def _show_status(self, msg: str) -> None:
        """Flash a message in the current-value label briefly."""
        self._lbl_current.setText(msg)
        QTimer.singleShot(3000, lambda: self._refresh_live_values())
