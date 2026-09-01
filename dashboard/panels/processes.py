"""
dashboard/panels/processes.py — Process Manager tab.

Features:
  - Sortable table: PID, Name, State, CPU ticks, Threads
  - Uses psutil for richer live process info (CPU%, Memory MB, nice)
  - Kill (SIGTERM), Force-kill (SIGKILL), Re-nice buttons
  - Search/filter bar
  - Auto-refreshes every snapshot tick
"""

from __future__ import annotations

import logging
import os
import signal

import psutil
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QSortFilterProxyModel, QTimer, QRectF
from PyQt6.QtGui import QStandardItem, QStandardItemModel, QColor, QPainter, QBrush, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QInputDialog,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTableView,
    QVBoxLayout, QWidget,
)

from dashboard import theme
from dashboard.widgets import AlertBanner, SectionHeader
from monitor.types import SystemSnapshot

logger = logging.getLogger(__name__)

_HEADERS = ["PID", "Name", "State", "CPU %", "Mem MB", "Threads", "Nice"]
_PID_COL   = 0
_NAME_COL  = 1
_STATE_COL = 2
_CPU_COL   = 3
_MEM_COL   = 4
_THR_COL   = 5
_NICE_COL  = 6

_STATE_COLORS = {
    "S": theme.ACCENT2,   # sleeping
    "R": theme.ACCENT,    # running
    "D": theme.WARN,      # uninterruptible sleep
    "Z": theme.DANGER,    # zombie
    "T": theme.TEXT_SEC,  # stopped
    "I": theme.TEXT_DIM,  # idle kernel thread
}


class StackedUsageBar(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(115)
        self.title = title
        self.data = []
        self.unallocated = 100.0
        self.max_val = 100.0

    def update_data(self, data, max_val: float):
        colors = [QColor(c) for c in theme.PLOT_COLORS]
        
        total_used = sum(v for _, v in data)
        self.max_val = max_val
        
        self.data = []
        for i, (name, val) in enumerate(data):
            c = QColor("#555555") if name == "Other" else colors[i % len(colors)]
            self.data.append((name, val, c))
            
        self.unallocated = max(0.0, self.max_val - total_used)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        
        p.setPen(QColor(theme.TEXT_PRI))
        p.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        p.drawText(QRectF(0, 0, w, 20), Qt.AlignmentFlag.AlignLeft, self.title)
        
        y_offset = 28
        bar_h = 24
        bg_rect = QRectF(0, y_offset, w, bar_h)
        p.setBrush(QBrush(QColor(theme.BG_DEEP)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(bg_rect, 4, 4)
        
        x = 0.0
        for name, val, color in self.data:
            if self.max_val > 0:
                segment_w = (val / self.max_val) * w
                if segment_w > 0:
                    rect = QRectF(x, y_offset, segment_w, bar_h)
                    p.setBrush(QBrush(color))
                    p.drawRect(rect)
                    x += segment_w

        p.setPen(QColor(theme.TEXT_SEC))
        p.setFont(QFont("Inter", 10))
        
        leg_x = 0.0
        leg_y = y_offset + bar_h + 18
        
        items = self.data + [("Idle/Free", self.unallocated, QColor(theme.BG_DEEP))]
        
        for name, val, color in items:
            pct = (val / self.max_val) * 100 if self.max_val > 0 else 0
            if pct < 0.5 and name != "Idle/Free": continue
            text = f"{name} ({pct:.1f}%)"
            
            text_w = p.fontMetrics().horizontalAdvance(text) + 30
            if leg_x + text_w > w:
                leg_x = 0.0
                leg_y += 18
            
            p.setBrush(QBrush(color))
            p.drawRect(QRectF(leg_x, leg_y - 10, 12, 12))
            p.drawText(QRectF(leg_x + 18, leg_y - 11, text_w, 15), Qt.AlignmentFlag.AlignLeft, text)
            
            leg_x += text_w + 5
            
        p.end()


class ProcessPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        # ── Alert banner (shown on permission errors) ─────────────────────
        self._alert = AlertBanner(
            "Kill/re-nice requires root or matching UID. Some actions may fail.",
            level="warn",
        )
        root.addWidget(self._alert)

        root.addWidget(SectionHeader("Process Manager"))

        # ── Toolbar ───────────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Filter by name or PID…")
        self._search.setMaximumWidth(320)

        self._btn_refresh = QPushButton("⟳  Refresh")
        self._btn_kill    = QPushButton("⬛  Terminate")
        self._btn_kill.setObjectName("btn_danger")
        self._btn_kill9   = QPushButton("✖  Force Kill")
        self._btn_kill9.setObjectName("btn_danger")
        self._btn_renice  = QPushButton("↕  Re-nice")
        self._btn_renice.setObjectName("btn_warn")

        self._lbl_count = QLabel("0 processes")
        self._lbl_count.setStyleSheet(f"color: {theme.TEXT_SEC}; font-size: 12px;")

        toolbar.addWidget(self._search)
        toolbar.addStretch()
        toolbar.addWidget(self._lbl_count)
        toolbar.addWidget(self._btn_refresh)
        toolbar.addWidget(self._btn_renice)
        toolbar.addWidget(self._btn_kill)
        toolbar.addWidget(self._btn_kill9)
        root.addLayout(toolbar)

        # ── Top Apps Charts ───────────────────────────────────────────────
        charts_layout = QHBoxLayout()
        charts_layout.setSpacing(20)
        self._cpu_chart = StackedUsageBar("CPU Usage")
        self._mem_chart = StackedUsageBar("Memory Usage")
        charts_layout.addWidget(self._cpu_chart)
        charts_layout.addWidget(self._mem_chart)
        root.addLayout(charts_layout)

        # ── Table ─────────────────────────────────────────────────────────
        self._model = QStandardItemModel(0, len(_HEADERS))
        self._model.setHorizontalHeaderLabels(_HEADERS)

        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)  # search all columns
        self._proxy.setSortRole(Qt.ItemDataRole.UserRole)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(_MEM_COL, Qt.SortOrder.DescendingOrder)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            _NAME_COL, QHeaderView.ResizeMode.Stretch
        )
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.setStyleSheet(f"""
            QTableView {{
                background: {theme.BG_CARD};
                alternate-background-color: {theme.BG_DEEP};
                gridline-color: {theme.BORDER};
                border-radius: 8px;
                font-size: 12px;
            }}
            QTableView::item:selected {{
                background: #1f6feb33;
                color: {theme.ACCENT};
            }}
        """)

        root.addWidget(self._table)

        # ── Connections ───────────────────────────────────────────────────
        self._search.textChanged.connect(self._proxy.setFilterFixedString)
        self._btn_refresh.clicked.connect(self._refresh_psutil)
        self._btn_kill.clicked.connect(lambda: self._signal_selected(signal.SIGTERM))
        self._btn_kill9.clicked.connect(lambda: self._signal_selected(signal.SIGKILL))
        self._btn_renice.clicked.connect(self._renice_selected)

        # Initial load
        self._refresh_psutil()

    # ── Data ingestion ────────────────────────────────────────────────────
    def update_snapshot(self, snap: SystemSnapshot) -> None:
        """Called every tick from the main window."""
        self._refresh_psutil()

    def _refresh_psutil(self) -> None:
        self._model.removeRows(0, self._model.rowCount())
        try:
            procs = list(psutil.process_iter(
                ["pid", "name", "status", "cpu_percent", "memory_info", "num_threads", "nice"]
            ))
        except Exception as exc:
            logger.warning("psutil.process_iter failed: %s", exc)
            return

        for proc in procs:
            try:
                info = proc.info
                pid      = info.get("pid", 0)
                name     = info.get("name", "?") or "?"
                state    = (info.get("status", "?") or "?")[0].upper()
                cpu_pct  = info.get("cpu_percent") or 0.0
                mem_mb   = (info.get("memory_info") and info["memory_info"].rss / 1e6) or 0.0
                threads  = info.get("num_threads") or 0
                nice     = info.get("nice") or 0

                def _create_item(display_str, sort_value):
                    item = QStandardItem()
                    item.setData(display_str, Qt.ItemDataRole.DisplayRole)
                    item.setData(sort_value, Qt.ItemDataRole.UserRole)
                    return item

                row = [
                    _create_item(str(pid), pid),
                    _create_item(name, name.lower()),
                    _create_item(state, state),
                    _create_item(f"{cpu_pct:.1f}", cpu_pct),
                    _create_item(f"{mem_mb:.1f}", mem_mb),
                    _create_item(str(threads), threads),
                    _create_item(str(nice), nice),
                ]
                # PID and numeric cols — right-align for sorting
                for col in (_PID_COL, _CPU_COL, _MEM_COL, _THR_COL, _NICE_COL):
                    row[col].setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                # State colour
                state_color = _STATE_COLORS.get(state, theme.TEXT_SEC)
                row[_STATE_COL].setForeground(QColor(state_color))

                # High-CPU highlight
                if cpu_pct > 80:
                    for item in row:
                        item.setForeground(QColor(theme.DANGER))

                self._model.appendRow(row)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        self._lbl_count.setText(f"{self._model.rowCount()} processes")

        # Update CPU Chart
        top_cpu = sorted(procs, key=lambda p: (p.info.get("cpu_percent") or 0.0), reverse=True)[:6]
        cpu_chart_data = [
            (p.info.get("name") or "?", p.info.get("cpu_percent") or 0.0)
            for p in top_cpu if (p.info.get("cpu_percent") or 0.0) > 0.0
        ]
        num_cores = psutil.cpu_count() or 1
        max_cpu = num_cores * 100.0
        overall_cpu = psutil.cpu_percent(interval=None) / 100.0 * max_cpu
        top_6_cpu = sum(val for _, val in cpu_chart_data)
        other_cpu = overall_cpu - top_6_cpu
        if other_cpu > 0:
            cpu_chart_data.append(("Other", other_cpu))
        self._cpu_chart.update_data(cpu_chart_data, max_val=max_cpu)
        
        # Update Memory Chart
        top_mem = sorted(procs, key=lambda p: ((p.info.get("memory_info") and p.info["memory_info"].rss) or 0.0), reverse=True)[:6]
        mem_chart_data = [
            (p.info.get("name") or "?", (p.info["memory_info"].rss / 1e6) if p.info.get("memory_info") else 0.0)
            for p in top_mem if p.info.get("memory_info") and p.info["memory_info"].rss > 0
        ]
        try:
            vmem = psutil.virtual_memory()
            total_mem_mb = vmem.total / 1e6
            available_mem_mb = vmem.available / 1e6
            top_6_mem = sum(val for _, val in mem_chart_data)
            other_mem = total_mem_mb - available_mem_mb - top_6_mem
            if other_mem > 0:
                mem_chart_data.append(("Other", other_mem))
        except Exception:
            total_mem_mb = 100.0
        self._mem_chart.update_data(mem_chart_data, max_val=total_mem_mb)

    # ── Actions ───────────────────────────────────────────────────────────
    def _selected_pid(self) -> int | None:
        idx = self._table.selectionModel().selectedRows()
        if not idx:
            return None
        src_idx = self._proxy.mapToSource(idx[0])
        try:
            return int(self._model.item(src_idx.row(), _PID_COL).text())
        except (ValueError, AttributeError):
            return None

    def _signal_selected(self, sig: signal.Signals) -> None:
        pid = self._selected_pid()
        if pid is None:
            QMessageBox.information(self, "No selection", "Select a process first.")
            return
        name = self._model.item(
            self._proxy.mapToSource(self._table.selectionModel().selectedRows()[0]).row(),
            _NAME_COL,
        ).text()
        confirm = QMessageBox.question(
            self, "Confirm",
            f"Send {'SIGTERM' if sig == signal.SIGTERM else 'SIGKILL'} to {name} (PID {pid})?",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                os.kill(pid, sig)
            except PermissionError:
                QMessageBox.critical(self, "Permission denied",
                                     f"Cannot signal PID {pid} — permission denied.")
            except ProcessLookupError:
                QMessageBox.warning(self, "Not found", f"PID {pid} no longer exists.")
            self._refresh_psutil()

    def _renice_selected(self) -> None:
        pid = self._selected_pid()
        if pid is None:
            QMessageBox.information(self, "No selection", "Select a process first.")
            return
        value, ok = QInputDialog.getInt(
            self, "Re-nice", f"New nice value for PID {pid} (-20 to 19):",
            value=0, min=-20, max=19,
        )
        if ok:
            try:
                psutil.Process(pid).nice(value)
            except (psutil.AccessDenied, psutil.NoSuchProcess) as exc:
                QMessageBox.critical(self, "Error", str(exc))
            self._refresh_psutil()
