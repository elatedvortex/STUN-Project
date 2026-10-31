"""
dashboard/widgets.py — Reusable, themed PyQt6 widget components.

Components
----------
StatCard        — headline metric card (big number + label + optional bar)
RingGauge       — circular gauge using QPainter
MiniSparkline   — tiny inline pyqtgraph sparkline
SectionHeader   — styled divider label
AlertBanner     — dismissable warning / error banner
"""

from __future__ import annotations

import math
from collections import deque
from typing import Optional

import pyqtgraph as pg
from PyQt6.QtCore import Qt, QRectF, QTimer
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPainterPath, QPen, QBrush, QLinearGradient,
)
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout,
    QWidget,
)

from dashboard import theme


# ── helpers ───────────────────────────────────────────────────────────────

def _color(hex_str: str) -> QColor:
    return QColor(hex_str)


def _lerp_color(c1: str, c2: str, t: float) -> QColor:
    """Linear interpolation between two hex colors at position t ∈ [0,1]."""
    a, b = QColor(c1), QColor(c2)
    r = int(a.red()   + (b.red()   - a.red())   * t)
    g = int(a.green() + (b.green() - a.green()) * t)
    bl= int(a.blue()  + (b.blue()  - a.blue())  * t)
    return QColor(r, g, bl)


def _value_color(pct: float) -> str:
    """Map 0-100 → green→amber→red."""
    if pct < 60:
        return theme.ACCENT2
    elif pct < 80:
        return theme.WARN
    return theme.DANGER


# ── RingGauge ────────────────────────────────────────────────────────────

class RingGauge(QWidget):
    """Circular arc gauge. `value` ∈ [0, 100]."""

    def __init__(
        self,
        title: str = "",
        size: int = 120,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._value: float = 0.0
        self._size = size
        self.setFixedSize(size, size)
        self.setToolTip(title)

    def setValue(self, v: float) -> None:
        self._value = max(0.0, min(100.0, v))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        margin = 10
        rect = QRectF(margin, margin, w - 2 * margin, h - 2 * margin)

        # Background track
        pen = QPen(_color(theme.BORDER), 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, 225 * 16, -270 * 16)

        # Value arc
        color_hex = _value_color(self._value)
        pen2 = QPen(_color(color_hex), 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen2)
        span = int(-270 * 16 * (self._value / 100))
        p.drawArc(rect, 225 * 16, span)

        # Centre text
        p.setPen(_color(theme.TEXT_PRI))
        font = QFont("Inter", int(self._size * 0.14), QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{self._value:.0f}%")

        # Title below
        if self._title:
            title_rect = QRectF(0, h - 20, w, 18)
            p.setPen(_color(theme.TEXT_SEC))
            small = QFont("Inter", 9)
            p.setFont(small)
            p.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, self._title)

        p.end()


# ── StatCard ─────────────────────────────────────────────────────────────

class StatCard(QFrame):
    """Compact metric card: big coloured number + unit + label + optional bar."""

    def __init__(
        self,
        label: str,
        unit: str = "",
        show_bar: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._show_bar = show_bar
        self._pct: float = 0.0

        self.setObjectName("stat_card")
        self.setStyleSheet(f"""
            QFrame#stat_card {{
                background: {theme.BG_CARD};
                border: 1px solid {theme.BORDER};
                border-radius: 12px;
            }}
            QFrame#stat_card:hover {{
                border-color: {theme.ACCENT};
                background: {theme.BG_HOVER};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(4)

        lbl = QLabel(label.upper())
        lbl.setObjectName("stat_label")
        lbl.setStyleSheet(f"color: {theme.TEXT_SEC}; font-size: 10px; font-weight: 600; letter-spacing: 1px;")

        self._val_lbl = QLabel("—")
        self._val_lbl.setObjectName("stat_value")
        self._val_lbl.setStyleSheet(f"color: {theme.ACCENT}; font-size: 24px; font-weight: 700;")

        self._unit_lbl = QLabel(unit)
        self._unit_lbl.setStyleSheet(f"color: {theme.TEXT_SEC}; font-size: 11px;")

        top_row = QHBoxLayout()
        top_row.addWidget(self._val_lbl)
        top_row.addWidget(self._unit_lbl, alignment=Qt.AlignmentFlag.AlignBottom)
        top_row.addStretch()

        root.addWidget(lbl)
        root.addLayout(top_row)

        if show_bar:
            self._bar = _MiniBar()
            root.addWidget(self._bar)

    def update_value(self, text: str, pct: Optional[float] = None) -> None:
        self._val_lbl.setText(text)
        if pct is not None:
            color = _value_color(pct)
            self._val_lbl.setStyleSheet(
                f"color: {color}; font-size: 24px; font-weight: 700;"
            )
            if self._show_bar:
                self._bar.setValue(pct)


class _MiniBar(QWidget):
    """Thin progress bar used inside StatCard."""

    def __init__(self) -> None:
        super().__init__()
        self._value: float = 0.0
        self.setFixedHeight(4)

    def setValue(self, v: float) -> None:
        self._value = max(0.0, min(100.0, v))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # track
        p.setBrush(QBrush(_color(theme.BORDER)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, w, h, 2, 2)

        # fill
        fill_w = int(w * self._value / 100)
        if fill_w > 0:
            grad = QLinearGradient(0, 0, fill_w, 0)
            c = _value_color(self._value)
            grad.setColorAt(0, _color(theme.ACCENT))
            grad.setColorAt(1, _color(c))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(0, 0, fill_w, h, 2, 2)

        p.end()


# ── SparklineChart ────────────────────────────────────────────────────────

class SparklineChart(QWidget):
    """
    A pyqtgraph PlotWidget with a single scrolling line.
    max_points controls the history window.
    """

    def __init__(
        self,
        title: str = "",
        y_label: str = "",
        color: str = theme.ACCENT,
        max_points: int = 60,
        y_range: tuple[float, float] = (0, 100),
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._data: deque[float] = deque(maxlen=max_points)
        self._color = color

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        if title:
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet(
                f"color: {theme.TEXT_SEC}; font-size: 11px; font-weight: 600;"
                f" text-transform: uppercase; letter-spacing: 1px;"
            )
            layout.addWidget(title_lbl)

        pg.setConfigOption("background", theme.PG_BG)
        pg.setConfigOption("foreground", theme.TEXT_SEC)

        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setYRange(*y_range)
        self._plot_widget.showGrid(x=False, y=True, alpha=0.15)
        self._plot_widget.getAxis("bottom").setStyle(tickLength=0)
        self._plot_widget.getAxis("left").setLabel(y_label, color=theme.TEXT_DIM)
        self._plot_widget.getAxis("left").setStyle(tickLength=3)
        self._plot_widget.getPlotItem().setContentsMargins(4, 4, 4, 4)
        self._plot_widget.setMinimumHeight(110)

        # Fill under the curve
        fill = QColor(color)
        fill.setAlpha(36)
        self._curve = self._plot_widget.plot(
            pen=pg.mkPen(color=color, width=2),
            fillLevel=0,
            brush=pg.mkBrush(fill),
        )

        layout.addWidget(self._plot_widget)

    def append(self, value: float) -> None:
        self._data.append(value)
        self._curve.setData(list(self._data))


# ── MultiLineChart ────────────────────────────────────────────────────────

class MultiLineChart(QWidget):
    """Multi-series pyqtgraph chart (used for per-core CPU or multi-metric)."""

    def __init__(
        self,
        series_names: list[str],
        title: str = "",
        y_range: tuple[float, float] = (0, 100),
        max_points: int = 60,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if title:
            t = QLabel(title)
            t.setStyleSheet(f"color:{theme.TEXT_SEC};font-size:11px;font-weight:600;")
            layout.addWidget(t)

        pg.setConfigOption("background", theme.PG_BG)
        self._pw = pg.PlotWidget()
        self._pw.setYRange(*y_range)
        self._pw.showGrid(x=False, y=True, alpha=0.15)
        self._pw.setMinimumHeight(130)
        self._pw.addLegend(offset=(-10, 10))
        layout.addWidget(self._pw)

        self._data: dict[str, deque] = {n: deque(maxlen=max_points) for n in series_names}
        self._curves: dict[str, pg.PlotDataItem] = {}
        for i, name in enumerate(series_names):
            color = theme.PLOT_COLORS[i % len(theme.PLOT_COLORS)]
            self._curves[name] = self._pw.plot(
                pen=pg.mkPen(color=color, width=2),
                name=name,
            )

    def append(self, series_name: str, value: float) -> None:
        if series_name in self._data:
            self._data[series_name].append(value)
            self._curves[series_name].setData(list(self._data[series_name]))


# ── SectionHeader ─────────────────────────────────────────────────────────

class SectionHeader(QWidget):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 4)
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 10px; font-weight: 700;"
            " letter-spacing: 2px;"
        )
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {theme.BORDER};")
        layout.addWidget(lbl)
        layout.addWidget(line)


# ── AlertBanner ───────────────────────────────────────────────────────────

class AlertBanner(QFrame):
    """Dismissable colour-coded banner for warnings / errors."""

    def __init__(self, text: str, level: str = "warn", parent=None) -> None:
        super().__init__(parent)
        color = theme.WARN if level == "warn" else theme.DANGER
        self.setStyleSheet(f"""
            QFrame {{
                background: {color}22;
                border: 1px solid {color};
                border-radius: 8px;
                padding: 6px;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 8, 6)
        icon = "⚠" if level == "warn" else "✖"
        lbl = QLabel(f"{icon}  {text}")
        lbl.setStyleSheet(f"color: {color}; font-size: 12px;")
        lbl.setWordWrap(True)
        close = QPushButton("✕")
        close.setFixedSize(20, 20)
        close.setStyleSheet(
            f"background: transparent; color: {color}; border: none; font-size: 11px;"
        )
        close.clicked.connect(self.hide)
        layout.addWidget(lbl, 1)
        layout.addWidget(close)
