"""
dashboard/panels/experiment_history.py — Experiment History panel.

Reads real data from the SQLite benchmark_result + applied_config tables
and the checkpoints directory to surface a complete experiment history.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from dashboard import theme

import pyqtgraph as pg


def _styled_table(columns: list[str]) -> QTableWidget:
    t = QTableWidget()
    t.setColumnCount(len(columns))
    t.setHorizontalHeaderLabels(columns)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setAlternatingRowColors(True)
    t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    return t


class ExperimentHistoryPanel(QWidget):
    """Shows the complete history of benchmarks, config changes, and checkpoints."""

    def __init__(self, db_path: str = "data/experiments.db",
                 checkpoint_dir: str = "data/checkpoints",
                 parent=None) -> None:
        super().__init__(parent)
        self._db_path = db_path
        self._ckpt_dir = Path(checkpoint_dir)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Experiment History")
        title.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {theme.TEXT_PRI}; border: none;")
        hdr.addWidget(title)
        hdr.addStretch()

        self._btn_refresh = QPushButton("↻  Refresh")
        self._btn_refresh.clicked.connect(self.refresh)
        hdr.addWidget(self._btn_refresh)

        root.addLayout(hdr)

        # Summary strip
        self._summary = QLabel("Loading…")
        self._summary.setStyleSheet(
            f"color: {theme.TEXT_SEC}; font-size: 12px; border: none;"
        )
        root.addWidget(self._summary)

        # ── Splitter: table left, reward chart right ───────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        # Benchmark results table
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(8)

        lbl_bm = QLabel("BENCHMARK RESULTS")
        lbl_bm.setStyleSheet(
            f"color: {theme.TEXT_SEC}; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; border: none;"
        )
        left_lay.addWidget(lbl_bm)

        self._tbl_benchmarks = _styled_table(
            ["Timestamp", "Adapter", "Workload", "Score", "Status", "Tag"]
        )
        self._tbl_benchmarks.itemSelectionChanged.connect(self._on_benchmark_selected)
        left_lay.addWidget(self._tbl_benchmarks)

        splitter.addWidget(left)

        # Chart + applied configs
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(8)

        lbl_chart = QLabel("BENCHMARK SCORES OVER TIME")
        lbl_chart.setStyleSheet(
            f"color: {theme.TEXT_SEC}; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; border: none;"
        )
        right_lay.addWidget(lbl_chart)

        self._chart = pg.PlotWidget()
        self._chart.setBackground(theme.BG_CARD)
        self._chart.showGrid(x=True, y=True, alpha=0.08)
        self._chart.setLabel("left", "Score", color=theme.TEXT_SEC)
        self._chart.setLabel("bottom", "Run #", color=theme.TEXT_SEC)
        self._chart.setMaximumHeight(180)
        right_lay.addWidget(self._chart)

        lbl_cfg = QLabel("CONFIG CHANGES (AUDIT TRAIL)")
        lbl_cfg.setStyleSheet(
            f"color: {theme.TEXT_SEC}; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; border: none;"
        )
        right_lay.addWidget(lbl_cfg)

        self._tbl_configs = _styled_table(
            ["Timestamp", "Parameter", "Old Value", "New Value", "Source"]
        )
        right_lay.addWidget(self._tbl_configs)

        splitter.addWidget(right)
        splitter.setSizes([550, 450])

        # ── Checkpoints section ───────────────────────────────────────────
        lbl_ckpts = QLabel("SAVED CHECKPOINTS")
        lbl_ckpts.setStyleSheet(
            f"color: {theme.TEXT_SEC}; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; border: none;"
        )
        root.addWidget(lbl_ckpts)

        self._tbl_ckpts = _styled_table(
            ["File", "Algorithm", "Steps (from name)", "Size", "Date Modified"]
        )
        self._tbl_ckpts.setMaximumHeight(160)
        root.addWidget(self._tbl_ckpts)

        # Auto-refresh
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(15_000)

        self.refresh()

    # ── Public ────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        self._load_benchmarks()
        self._load_configs()
        self._load_checkpoints()

    # ── Private helpers ───────────────────────────────────────────────────

    def _db(self):
        from storage.db import StorageBackend
        return StorageBackend(self._db_path)

    def _load_benchmarks(self) -> None:
        try:
            rows = self._db().recent_benchmark_results(limit=200)
        except Exception as exc:
            self._summary.setText(f"⚠  DB error: {exc}")
            rows = []

        self._tbl_benchmarks.setRowCount(0)
        scores_x, scores_y = [], []

        for i, row in enumerate(rows):
            self._tbl_benchmarks.insertRow(i)
            ts = row["timestamp"][:19].replace("T", " ")
            score = f"{row['score']:.4f}"
            status = "✓  OK" if row["success"] else "✗  FAIL"
            tag = row["tag"] or ""

            for j, val in enumerate([ts, row["name"], row["workload_type"],
                                      score, status, tag]):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if val.startswith("✓"):
                    item.setForeground(QColor(theme.ACCENT2))
                elif val.startswith("✗"):
                    item.setForeground(QColor(theme.DANGER))
                self._tbl_benchmarks.setItem(i, j, item)

            scores_x.append(i)
            scores_y.append(row["score"])

        # Chart
        self._chart.clear()
        if scores_y:
            pen = pg.mkPen(color=theme.ACCENT, width=2)
            brush = pg.mkBrush(color=theme.ACCENT + "44")
            self._chart.plot(scores_x, scores_y, pen=pen, fillLevel=0,
                             brush=brush, symbol="o", symbolSize=5,
                             symbolBrush=theme.ACCENT)

        n = len(rows)
        self._summary.setText(
            f"Showing {n} benchmark result(s)  •  "
            f"{sum(1 for r in rows if r['success'])} passed  •  "
            f"{sum(1 for r in rows if not r['success'])} failed"
        )

    def _load_configs(self) -> None:
        try:
            rows = self._db().recent_applied_configs(limit=100)
        except Exception:
            rows = []

        self._tbl_configs.setRowCount(0)
        for i, row in enumerate(rows):
            self._tbl_configs.insertRow(i)
            ts = row["timestamp"][:19].replace("T", " ")
            for j, val in enumerate([ts, row["param_name"],
                                      row["old_value"] or "—",
                                      row["new_value"],
                                      row["source"] or "—"]):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._tbl_configs.setItem(i, j, item)

    def _load_checkpoints(self) -> None:
        self._tbl_ckpts.setRowCount(0)
        if not self._ckpt_dir.is_dir():
            return

        files = sorted(
            self._ckpt_dir.glob("*.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for i, f in enumerate(files):
            self._tbl_ckpts.insertRow(i)
            algo = "SAC" if "sac" in f.name.lower() else "PPO"
            steps = "—"
            for part in f.stem.split("_"):
                if part.isdigit():
                    steps = f"{int(part):,}"
                    break
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            size = f"{f.stat().st_size / 1_048_576:.2f} MB"

            for j, val in enumerate([f.name, algo, steps, size, mtime]):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if j == 1:  # algo column
                    item.setForeground(QColor(theme.ACCENT))
                self._tbl_ckpts.setItem(i, j, item)

    def _on_benchmark_selected(self) -> None:
        pass   # future: show metrics breakdown in a side panel
