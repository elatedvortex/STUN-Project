"""
dashboard/panels/log_viewer.py — Real-time log viewer panel.

Tails the application log file (or captures Python logging output) and
streams new lines into a scrollable text area with colour-coded severity.
"""
from __future__ import annotations
import logging
import os
from collections import deque
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QTextCursor
from PyQt6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QPlainTextEdit, QVBoxLayout, QWidget, QComboBox,
)
from dashboard import theme

# ── In-process log handler ─────────────────────────────────────────────────

class _QueueHandler(logging.Handler):
    """Captures log records to a deque for the GUI to consume."""
    def __init__(self, buf: deque):
        super().__init__()
        self._buf = buf

    def emit(self, record: logging.LogRecord) -> None:
        self._buf.append(record)


# ── Panel ──────────────────────────────────────────────────────────────────

class LogViewerPanel(QWidget):
    """Streams Python log records (and optionally a log file) into a rich viewer."""

    # Colour map
    _LEVEL_COLORS = {
        "DEBUG":    "#6b7280",   # gray
        "INFO":     "#a1a1aa",
        "WARNING":  "#f59e0b",
        "ERROR":    "#ef4444",
        "CRITICAL": "#dc2626",
    }

    def __init__(self, log_file: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self._log_file    = Path(log_file) if log_file else None
        self._file_offset = 0
        self._buf: deque[logging.LogRecord] = deque(maxlen=5000)
        self._paused = False

        # Attach to root logger
        self._handler = _QueueHandler(self._buf)
        self._handler.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
                              datefmt="%H:%M:%S")
        )
        logging.getLogger().addHandler(self._handler)
        logging.getLogger().setLevel(logging.DEBUG)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # ── Header ─────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("Log Viewer")
        title.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {theme.TEXT_PRI}; border: none;")
        hdr.addWidget(title)
        hdr.addStretch()

        self._cmb_level = QComboBox()
        self._cmb_level.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self._cmb_level.setCurrentText("INFO")
        self._cmb_level.setFixedWidth(110)
        hdr.addWidget(QLabel("Min Level:"))
        hdr.addWidget(self._cmb_level)

        self._inp_filter = QLineEdit()
        self._inp_filter.setPlaceholderText("Filter text…")
        self._inp_filter.setFixedWidth(180)
        hdr.addWidget(self._inp_filter)

        self._chk_scroll = QCheckBox("Auto-scroll")
        self._chk_scroll.setChecked(True)
        self._chk_scroll.setStyleSheet(f"color: {theme.TEXT_SEC}; border: none;")
        hdr.addWidget(self._chk_scroll)

        self._btn_pause = QPushButton("⏸  Pause")
        self._btn_pause.setCheckable(True)
        self._btn_pause.toggled.connect(self._toggle_pause)
        hdr.addWidget(self._btn_pause)

        self._btn_clear = QPushButton("🗑  Clear")
        self._btn_clear.clicked.connect(self._clear)
        hdr.addWidget(self._btn_clear)

        root.addLayout(hdr)

        # ── Text area ──────────────────────────────────────────────────────
        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setFont(QFont("JetBrains Mono, Consolas, monospace", 11))
        self._text.setStyleSheet(f"""
            QPlainTextEdit {{
                background: {theme.BG_CARD};
                color: {theme.TEXT_PRI};
                border: 1px solid {theme.BORDER};
                border-radius: 10px;
                padding: 10px;
                font-family: "JetBrains Mono", "Consolas", monospace;
                font-size: 11px;
            }}
        """)
        self._text.setMaximumBlockCount(5000)
        root.addWidget(self._text, 1)

        # ── Status bar ─────────────────────────────────────────────────────
        self._lbl_count = QLabel("0 lines")
        self._lbl_count.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 11px; border: none;")
        root.addWidget(self._lbl_count)

        # ── Timer ──────────────────────────────────────────────────────────
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._flush)
        self._timer.start(500)

    def closeEvent(self, event):
        logging.getLogger().removeHandler(self._handler)
        super().closeEvent(event)

    # ── Private ────────────────────────────────────────────────────────────

    def _toggle_pause(self, checked: bool) -> None:
        self._paused = checked
        self._btn_pause.setText("▶  Resume" if checked else "⏸  Pause")

    def _clear(self) -> None:
        self._text.clear()
        self._buf.clear()

    def _flush(self) -> None:
        if self._paused:
            return

        min_level = getattr(logging, self._cmb_level.currentText(), logging.DEBUG)
        filter_text = self._inp_filter.text().lower()

        new_html = []
        while self._buf:
            record = self._buf.popleft()
            if record.levelno < min_level:
                continue
            msg = self._handler.format(record)
            if filter_text and filter_text not in msg.lower():
                continue
            color = theme.resolve_color(self._LEVEL_COLORS.get(record.levelname, theme.TEXT_PRI))
            # Escape HTML
            msg_esc = msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            new_html.append(f'<span style="color:{color};">{msg_esc}</span>')

        # Also tail file if configured
        if self._log_file and self._log_file.is_file():
            try:
                with open(self._log_file, "r") as f:
                    f.seek(self._file_offset)
                    lines = f.readlines()
                    self._file_offset = f.tell()
                for line in lines:
                    line = line.rstrip()
                    if not line:
                        continue
                    if filter_text and filter_text not in line.lower():
                        continue
                    color = theme.TEXT_PRI
                    for lvl, c in self._LEVEL_COLORS.items():
                        if lvl in line:
                            color = c
                            break
                    line_esc = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    new_html.append(f'<span style="color:{color};">{line_esc}</span>')
            except Exception:
                pass

        if new_html:
            cursor = self._text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            for html in new_html:
                self._text.appendHtml(html)

            if self._chk_scroll.isChecked():
                self._text.ensureCursorVisible()
                sb = self._text.verticalScrollBar()
                sb.setValue(sb.maximum())

        self._lbl_count.setText(
            f"{self._text.blockCount()} lines  •  "
            f"Filter: {'active' if filter_text else 'none'}  •  "
            f"Level: {self._cmb_level.currentText()}"
        )
