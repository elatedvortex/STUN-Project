"""
dashboard/panels/memory.py — Memory Detail tab.

Shows:
  - Large stat cards: Total, Used, Available, Swap used
  - Used vs Available donut-style bar
  - Scrolling history chart for RAM + Swap
  - psutil-based memory breakdown: buffers, cached, shmem
"""

from __future__ import annotations

import psutil
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy,
    QVBoxLayout, QWidget,
)

from dashboard import theme
from dashboard.widgets import SectionHeader, SparklineChart, StatCard, MultiLineChart
from monitor.types import SystemSnapshot


def _kb_to_human(kb: int | None) -> str:
    if kb is None:
        return "—"
    if kb >= 1_048_576:
        return f"{kb / 1_048_576:.1f} GB"
    return f"{kb / 1024:.0f} MB"


class MemoryPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        root.addWidget(SectionHeader("Memory Overview"))

        # ── Stat cards ────────────────────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)

        self._card_total  = StatCard("Total RAM",   show_bar=False)
        self._card_used   = StatCard("Used",         show_bar=True)
        self._card_avail  = StatCard("Available",    show_bar=False)
        self._card_cached = StatCard("Cached",       show_bar=False)
        self._card_swap   = StatCard("Swap Used",    show_bar=True)

        for c in (self._card_total, self._card_used, self._card_avail,
                  self._card_cached, self._card_swap):
            c.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            cards_row.addWidget(c)

        root.addLayout(cards_row)

        # ── psutil breakdown ──────────────────────────────────────────────
        root.addWidget(SectionHeader("Breakdown (psutil)"))

        breakdown_row = QHBoxLayout()
        breakdown_row.setSpacing(12)

        self._card_buffers = StatCard("Buffers",  show_bar=False)
        self._card_shmem   = StatCard("Shared",   show_bar=False)
        self._card_sreclm  = StatCard("Reclaimable", show_bar=False)
        self._card_anon    = StatCard("Anonymous", show_bar=False)

        for c in (self._card_buffers, self._card_shmem, self._card_sreclm, self._card_anon):
            c.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            breakdown_row.addWidget(c)

        root.addLayout(breakdown_row)

        # ── Charts ────────────────────────────────────────────────────────
        root.addWidget(SectionHeader("History (60s)"))

        charts_row = QHBoxLayout()
        self._chart_ram = SparklineChart(
            title="RAM Utilisation %",
            y_label="%",
            color=theme.ACCENT2,
            y_range=(0, 100),
        )
        self._chart_swap = SparklineChart(
            title="Swap Utilisation %",
            y_label="%",
            color=theme.DANGER,
            y_range=(0, 100),
        )
        for ch in (self._chart_ram, self._chart_swap):
            ch.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            charts_row.addWidget(ch)
        root.addLayout(charts_row)
        root.addStretch()

    def update_snapshot(self, snap: SystemSnapshot) -> None:
        # From SystemSnapshot
        mem_pct  = snap.mem_util_pct or 0.0
        used_kb  = (
            (snap.mem_total_kb or 0) - (snap.mem_available_kb or 0)
        )
        swap_total = snap.swap_total_kb or 0
        swap_free  = snap.swap_free_kb  or 0
        swap_used  = swap_total - swap_free
        swap_pct   = 100.0 * swap_used / swap_total if swap_total else 0.0

        self._card_total.update_value(_kb_to_human(snap.mem_total_kb))
        self._card_used.update_value(_kb_to_human(used_kb), pct=mem_pct)
        self._card_avail.update_value(_kb_to_human(snap.mem_available_kb))
        self._card_swap.update_value(_kb_to_human(swap_used), pct=swap_pct)

        # psutil for richer breakdown
        try:
            vm = psutil.virtual_memory()
            self._card_cached.update_value(_kb_to_human(getattr(vm, "cached", 0) // 1024))
            self._card_buffers.update_value(_kb_to_human(getattr(vm, "buffers", 0) // 1024))
            self._card_shmem.update_value(_kb_to_human(getattr(vm, "shared", 0) // 1024))
            # reclaimable = cached + buffers approx
            reclaimable = (getattr(vm, "cached", 0) + getattr(vm, "buffers", 0)) // 1024
            self._card_sreclm.update_value(_kb_to_human(reclaimable))
            anon_kb = (vm.used - getattr(vm, "buffers", 0) - getattr(vm, "cached", 0)) // 1024
            self._card_anon.update_value(_kb_to_human(max(0, anon_kb)))
        except Exception:
            pass

        self._chart_ram.append(mem_pct)
        self._chart_swap.append(swap_pct)
