"""
dashboard/panels/overview.py — Overview tab.

Shows:
  - 4 gauge rings: CPU %, Memory %, Swap %, CPU freq
  - 3 sparkline charts: CPU util over time, Memory over time, Context switches/s
  - Stat cards: load avg 1/5/15, runnable procs, total procs
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from dashboard import theme
from dashboard.widgets import (
    MultiLineChart, RingGauge, SectionHeader, SparklineChart, StatCard,
)
from monitor.types import SystemSnapshot


class OverviewPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(16)

        # ── Gauges row ───────────────────────────────────────────────────
        root.addWidget(SectionHeader("Live Metrics"))
        gauge_row = QHBoxLayout()
        gauge_row.setSpacing(20)

        self._gauge_cpu  = RingGauge("CPU",    size=130)
        self._gauge_mem  = RingGauge("Memory", size=130)
        self._gauge_swap = RingGauge("Swap",   size=130)
        self._gauge_freq = RingGauge("Freq",   size=130)

        for g in (self._gauge_cpu, self._gauge_mem, self._gauge_swap, self._gauge_freq):
            gauge_row.addWidget(g, alignment=Qt.AlignmentFlag.AlignHCenter)
        gauge_row.addStretch()
        root.addLayout(gauge_row)

        # ── Stat cards row ───────────────────────────────────────────────
        root.addWidget(SectionHeader("System Summary"))
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)

        self._card_load1  = StatCard("Load 1m",  show_bar=False)
        self._card_load5  = StatCard("Load 5m",  show_bar=False)
        self._card_load15 = StatCard("Load 15m", show_bar=False)
        self._card_run    = StatCard("Runnable",  show_bar=False)
        self._card_total  = StatCard("Processes", show_bar=False)
        self._card_ctxt   = StatCard("Ctxt/s",    show_bar=False)
        self._card_freq   = StatCard("CPU Freq",  unit="MHz", show_bar=False)

        for c in (
            self._card_load1, self._card_load5, self._card_load15,
            self._card_run, self._card_total, self._card_ctxt, self._card_freq
        ):
            c.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            cards_row.addWidget(c)
        root.addLayout(cards_row)

        # ── Sparkline charts ─────────────────────────────────────────────
        root.addWidget(SectionHeader("Historical (60s)"))

        charts_row = QHBoxLayout()
        charts_row.setSpacing(12)

        self._chart_cpu  = SparklineChart(
            title="CPU Utilisation %",
            y_label="%",
            color=theme.ACCENT,
            y_range=(0, 100),
        )
        self._chart_mem  = SparklineChart(
            title="Memory Utilisation %",
            y_label="%",
            color=theme.ACCENT2,
            y_range=(0, 100),
        )
        self._chart_ctxt = SparklineChart(
            title="Context Switches / tick",
            y_label="k/s",
            color=theme.WARN,
            y_range=(0, 5000),
        )

        for ch in (self._chart_cpu, self._chart_mem, self._chart_ctxt):
            ch.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            charts_row.addWidget(ch)

        root.addLayout(charts_row)
        root.addStretch()

    # ── Data ingestion ────────────────────────────────────────────────────
    def update_snapshot(self, snap: SystemSnapshot) -> None:
        cpu  = snap.cpu_util_pct or 0.0
        mem  = snap.mem_util_pct or 0.0
        freq = snap.cpu_freq_mhz or 0.0

        # swap %
        swap_total = snap.swap_total_kb or 0
        swap_free  = snap.swap_free_kb  or 0
        swap_pct   = (
            100.0 * (swap_total - swap_free) / swap_total
            if swap_total > 0 else 0.0
        )
        # freq gauge: normalise to 0-100 assuming max 5000 MHz
        freq_pct = min(100.0, freq / 50.0)  # 5000 MHz → 100%

        self._gauge_cpu.setValue(cpu)
        self._gauge_mem.setValue(mem)
        self._gauge_swap.setValue(swap_pct)
        self._gauge_freq.setValue(freq_pct)

        self._card_load1.update_value(f"{snap.load_avg_1:.2f}" if snap.load_avg_1 is not None else "—")
        self._card_load5.update_value(f"{snap.load_avg_5:.2f}" if snap.load_avg_5 is not None else "—")
        self._card_load15.update_value(f"{snap.load_avg_15:.2f}" if snap.load_avg_15 is not None else "—")
        self._card_run.update_value(str(snap.runnable_procs or "—"))
        self._card_total.update_value(str(snap.total_procs or "—"))
        self._card_ctxt.update_value(
            f"{snap.ctxt_switches_delta:,}" if snap.ctxt_switches_delta is not None else "—"
        )
        self._card_freq.update_value(
            f"{freq:.0f}" if freq else "—",
        )

        self._chart_cpu.append(cpu)
        self._chart_mem.append(mem)
        if snap.ctxt_switches_delta is not None:
            self._chart_ctxt.append(float(snap.ctxt_switches_delta))
