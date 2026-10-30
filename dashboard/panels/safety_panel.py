"""
dashboard/panels/safety_panel.py — Safety & Audit panel.
"""
from __future__ import annotations
from datetime import datetime
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from dashboard import theme
import pyqtgraph as pg


class SafetyPanel(QWidget):
    """Safety & audit-trail viewer backed by the SQLite storage layer."""

    def __init__(self, db_path: str = "data/experiments.db", parent=None) -> None:
        super().__init__(parent)
        self._db_path = db_path

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(16)

        hdr = QHBoxLayout()
        title = QLabel("Safety & Audit Trail")
        title.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {theme.TEXT_PRI}; border: none;")
        hdr.addWidget(title)
        hdr.addStretch()
        self._btn_refresh = QPushButton("↻  Refresh")
        self._btn_refresh.clicked.connect(self.refresh)
        hdr.addWidget(self._btn_refresh)
        root.addLayout(hdr)

        desc = QLabel(
            "All sysctl writes made by the SchedulerController are recorded here. "
            "SecondaryValidator → Validator → Writer → RollbackStack."
        )
        desc.setStyleSheet(f"color: {theme.TEXT_SEC}; font-size: 13px; border: none;")
        desc.setWordWrap(True)
        root.addWidget(desc)

        cards_row = QHBoxLayout()
        self._card_total   = self._kpi("Total Writes",  "—", theme.ACCENT)
        self._card_success = self._kpi("Successful",    "—", theme.ACCENT2)
        self._card_failed  = self._kpi("Failed",        "—", theme.DANGER)
        self._card_params  = self._kpi("Unique Params", "—", theme.WARN)
        for c in (self._card_total, self._card_success, self._card_failed, self._card_params):
            cards_row.addWidget(c)
        cards_row.addStretch()
        root.addLayout(cards_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        lbl_a = QLabel("APPLIED CONFIG AUDIT TRAIL")
        lbl_a.setStyleSheet(f"color: {theme.TEXT_SEC}; font-size: 11px; font-weight: 700; border: none;")
        ll.addWidget(lbl_a)
        self._tbl_audit = QTableWidget()
        self._tbl_audit.setColumnCount(6)
        self._tbl_audit.setHorizontalHeaderLabels(
            ["Timestamp", "Parameter", "Sysctl Path", "Old Value", "New Value", "Status"])
        self._tbl_audit.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._tbl_audit.verticalHeader().setVisible(False)
        self._tbl_audit.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tbl_audit.setAlternatingRowColors(True)
        ll.addWidget(self._tbl_audit)
        splitter.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        lbl_f = QLabel("PARAMETER WRITE FREQUENCY")
        lbl_f.setStyleSheet(f"color: {theme.TEXT_SEC}; font-size: 11px; font-weight: 700; border: none;")
        rl.addWidget(lbl_f)
        self._chart = pg.PlotWidget()
        self._chart.setBackground(theme.BG_CARD)
        self._chart.showGrid(x=False, y=True, alpha=0.08)
        self._chart.setLabel("left", "Count", color=theme.TEXT_SEC)
        rl.addWidget(self._chart)

        lbl_s = QLabel("WRITES BY SOURCE")
        lbl_s.setStyleSheet(f"color: {theme.TEXT_SEC}; font-size: 11px; font-weight: 700; border: none;")
        rl.addWidget(lbl_s)
        self._tbl_sources = QTableWidget()
        self._tbl_sources.setColumnCount(2)
        self._tbl_sources.setHorizontalHeaderLabels(["Source", "Count"])
        self._tbl_sources.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._tbl_sources.verticalHeader().setVisible(False)
        self._tbl_sources.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tbl_sources.setMaximumHeight(130)
        rl.addWidget(self._tbl_sources)
        splitter.addWidget(right)
        splitter.setSizes([620, 380])

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(10_000)
        self.refresh()

    def refresh(self) -> None:
        self._load_audit()

    def _db(self):
        from storage.db import StorageBackend
        return StorageBackend(self._db_path)

    def _load_audit(self) -> None:
        try:
            rows = self._db().recent_applied_configs(limit=500)
        except Exception:
            rows = []

        self._tbl_audit.setRowCount(0)
        param_counts: dict[str, int] = {}
        source_counts: dict[str, int] = {}
        n_ok = n_fail = 0

        for i, row in enumerate(rows):
            self._tbl_audit.insertRow(i)
            ts     = row["timestamp"][:19].replace("T", " ")
            status = "✓  OK" if row["success"] else "✗  FAIL"
            param  = row["param_name"]
            source = row["source"] or "—"
            param_counts[param]   = param_counts.get(param, 0) + 1
            source_counts[source] = source_counts.get(source, 0) + 1
            if row["success"]: n_ok += 1
            else: n_fail += 1

            for j, val in enumerate([ts, param, row["sysctl_path"],
                                      row["old_value"] or "—", row["new_value"], status]):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if j == 5:
                    item.setForeground(QColor(theme.ACCENT2 if "OK" in val else theme.DANGER))
                self._tbl_audit.setItem(i, j, item)

        self._card_total.findChildren(QLabel)[1].setText(str(len(rows)))
        self._card_success.findChildren(QLabel)[1].setText(str(n_ok))
        self._card_failed.findChildren(QLabel)[1].setText(str(n_fail))
        self._card_params.findChildren(QLabel)[1].setText(str(len(param_counts)))

        self._chart.clear()
        if param_counts:
            sorted_params = sorted(param_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            labels = [p[0].split(".")[-1] for p in sorted_params]
            values = [p[1] for p in sorted_params]
            bg = pg.BarGraphItem(x=list(range(len(labels))), height=values,
                                 width=0.6, brush=theme.ACCENT + "aa", pen=theme.ACCENT)
            self._chart.addItem(bg)
            ax = self._chart.getAxis("bottom")
            ax.setTicks([[(i, l) for i, l in enumerate(labels)]])

        self._tbl_sources.setRowCount(0)
        for i, (src, cnt) in enumerate(sorted(source_counts.items(), key=lambda x: x[1], reverse=True)):
            self._tbl_sources.insertRow(i)
            self._tbl_sources.setItem(i, 0, QTableWidgetItem(src))
            self._tbl_sources.setItem(i, 1, QTableWidgetItem(str(cnt)))

    @staticmethod
    def _kpi(label: str, value: str, color: str) -> QFrame:
        f = QFrame()
        f.setStyleSheet(f"QFrame {{ background: {theme.BG_CARD}; border: 1px solid {theme.BORDER}; border-radius: 10px; }}")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(2)
        lbl_l = QLabel(label.upper())
        lbl_l.setStyleSheet(f"color: {theme.TEXT_SEC}; font-size: 10px; font-weight: 700; border: none; background: transparent;")
        lbl_v = QLabel(value)
        lbl_v.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: 800; border: none; background: transparent;")
        lay.addWidget(lbl_l)
        lay.addWidget(lbl_v)
        return f
