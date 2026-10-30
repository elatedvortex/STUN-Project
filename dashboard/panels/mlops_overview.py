"""
dashboard/panels/mlops_overview.py — MLOps home panel.

The first page a user sees: a command-centre summary with experiment
stats, quick-action buttons, recent checkpoint activity, and a live
system health strip.  All data is read from the SQLite backend and the
filesystem; nothing is faked.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from dashboard import theme


# ── Helpers ──────────────────────────────────────────────────────────────────

def _card(title: str, value: str, color: str = theme.ACCENT, subtitle: str = "") -> QWidget:
    """Small KPI card widget."""
    w = QFrame()
    w.setStyleSheet(f"""
        QFrame {{
            background: {theme.BG_CARD};
            border: 1px solid {theme.BORDER};
            border-radius: 12px;
            padding: 4px;
        }}
    """)
    lay = QVBoxLayout(w)
    lay.setContentsMargins(20, 16, 20, 16)
    lay.setSpacing(4)

    lbl_title = QLabel(title.upper())
    lbl_title.setStyleSheet(
        f"color: {theme.TEXT_SEC}; font-size: 11px; font-weight: 700;"
        " letter-spacing: 1.2px; background: transparent; border: none;"
    )

    lbl_val = QLabel(value)
    lbl_val.setObjectName("stat_value")
    lbl_val.setStyleSheet(
        f"color: {color}; font-size: 28px; font-weight: 800;"
        " background: transparent; border: none;"
    )

    lay.addWidget(lbl_title)
    lay.addWidget(lbl_val)

    if subtitle:
        lbl_sub = QLabel(subtitle)
        lbl_sub.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 11px;"
            " background: transparent; border: none;"
        )
        lay.addWidget(lbl_sub)

    return w


def _section(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {theme.TEXT_SEC}; font-size: 12px; font-weight: 700;"
        " letter-spacing: 1.5px; text-transform: uppercase;"
        " padding-bottom: 6px; border-bottom: 1px solid #3f3f46;"
    )
    return lbl


def _quick_btn(label: str, color: str = theme.ACCENT) -> QPushButton:
    btn = QPushButton(label)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: transparent;
            color: {color};
            border: 1px solid {color};
            border-radius: 8px;
            padding: 8px 18px;
            font-weight: 700;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background: {color};
            color: #fff;
        }}
    """)
    btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return btn


# ── Panel ─────────────────────────────────────────────────────────────────────

class MLOpsOverviewPanel(QWidget):
    """Landing page / control-centre overview for the STUN-Project MLOps dashboard."""

    # Emitted when the user clicks a quick-action button
    navigate_requested = pyqtSignal(str)  # page name

    def __init__(self, checkpoint_dir: str = "data/checkpoints", parent=None) -> None:
        super().__init__(parent)
        self._ckpt_dir = Path(checkpoint_dir)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(24)

        # ── Title ─────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.setSpacing(12)

        title = QLabel("◈  STUN-Project MLOps")
        title.setFont(QFont("Inter", 22, QFont.Weight.ExtraBold))
        title.setStyleSheet(f"color: {theme.TEXT_PRI}; border: none;")

        subtitle = QLabel("Reinforcement Learning Experiment Control Centre")
        subtitle.setStyleSheet(f"color: {theme.TEXT_SEC}; font-size: 14px; border: none;")

        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(subtitle)
        root.addLayout(hdr)

        # ── KPI row ────────────────────────────────────────────────────────
        root.addWidget(_section("Experiment Statistics"))

        self._kpi_row = QHBoxLayout()
        self._kpi_row.setSpacing(16)

        self._kpi_checkpoints = _card("Checkpoints", "—", theme.ACCENT,    "saved models")
        self._kpi_total_steps = _card("Total Steps",  "—", theme.ACCENT2,  "trained so far")
        self._kpi_best_reward = _card("Best Reward",  "—", theme.WARN,     "across runs")
        self._kpi_db_snaps    = _card("DB Snapshots", "—", theme.TEXT_SEC, "system records")

        for k in (self._kpi_checkpoints, self._kpi_total_steps,
                  self._kpi_best_reward, self._kpi_db_snaps):
            k.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._kpi_row.addWidget(k)

        root.addLayout(self._kpi_row)

        # ── Quick actions ─────────────────────────────────────────────────
        root.addWidget(_section("Quick Actions"))

        actions_row = QHBoxLayout()
        actions_row.setSpacing(12)

        self._btn_new    = _quick_btn("＋  New Training",          theme.ACCENT)
        self._btn_live   = _quick_btn("▶  Live Monitor",           theme.ACCENT2)
        self._btn_ckpts  = _quick_btn("💾  Checkpoints",           theme.WARN)
        self._btn_sched  = _quick_btn("⚙  Scheduler Params",      theme.TEXT_SEC)
        self._btn_safety = _quick_btn("🛡  Safety Panel",          theme.DANGER)

        for btn, page in [
            (self._btn_new,    "New Training"),
            (self._btn_live,   "Live Training"),
            (self._btn_ckpts,  "Checkpoints"),
            (self._btn_sched,  "Scheduler Params"),
            (self._btn_safety, "Safety Panel"),
        ]:
            btn.clicked.connect(lambda checked, p=page: self.navigate_requested.emit(p))
            actions_row.addWidget(btn)

        actions_row.addStretch()
        root.addLayout(actions_row)

        # ── Recent checkpoints ─────────────────────────────────────────────
        root.addWidget(_section("Recent Checkpoints"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(200)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._ckpt_container = QWidget()
        self._ckpt_container.setStyleSheet("background: transparent;")
        self._ckpt_layout = QVBoxLayout(self._ckpt_container)
        self._ckpt_layout.setContentsMargins(0, 0, 0, 0)
        self._ckpt_layout.setSpacing(4)

        scroll.setWidget(self._ckpt_container)
        root.addWidget(scroll)

        # ── System status strip ────────────────────────────────────────────
        root.addWidget(_section("System Status"))

        self._status_strip = QLabel("Initialising…")
        self._status_strip.setStyleSheet(
            f"color: {theme.TEXT_SEC}; font-size: 12px; font-family: monospace; border: none;"
        )
        root.addWidget(self._status_strip)

        root.addStretch()

        # ── Auto-refresh ──────────────────────────────────────────────────
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(5000)   # refresh every 5 s

        self.refresh()

    # ── Public slot ────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload KPI cards and checkpoint list from disk / DB."""
        self._refresh_checkpoints()
        self._refresh_kpis()

    # ── Private helpers ────────────────────────────────────────────────────

    def _find_checkpoint_files(self) -> list[Path]:
        if not self._ckpt_dir.is_dir():
            return []
        files = sorted(
            self._ckpt_dir.glob("*.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return files[:20]

    def _refresh_checkpoints(self) -> None:
        # Clear old rows
        while self._ckpt_layout.count():
            item = self._ckpt_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        files = self._find_checkpoint_files()

        if not files:
            placeholder = QLabel("  No checkpoints found in data/checkpoints/")
            placeholder.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12px; border: none;")
            self._ckpt_layout.addWidget(placeholder)
            return

        for f in files:
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            size_mb = f.stat().st_size / 1_048_576
            algo = "SAC" if "sac" in f.name.lower() else "PPO"

            row = QFrame()
            row.setStyleSheet(f"""
                QFrame {{
                    background: {theme.BG_CARD};
                    border: 1px solid {theme.BORDER};
                    border-radius: 8px;
                }}
            """)
            rl = QHBoxLayout(row)
            rl.setContentsMargins(12, 6, 12, 6)

            icon = "🟢" if algo == "PPO" else "🔵"
            lbl = QLabel(f"{icon}  {f.name}")
            lbl.setStyleSheet(f"color: {theme.TEXT_PRI}; font-size: 12px; border: none;")

            lbl_algo = QLabel(algo)
            lbl_algo.setStyleSheet(f"color: {theme.ACCENT}; font-size: 11px; font-weight: 700; border: none;")

            lbl_meta = QLabel(f"{size_mb:.1f} MB  •  {mtime}")
            lbl_meta.setStyleSheet(f"color: {theme.TEXT_SEC}; font-size: 11px; border: none;")

            rl.addWidget(lbl)
            rl.addStretch()
            rl.addWidget(lbl_algo)
            rl.addSpacing(12)
            rl.addWidget(lbl_meta)

            self._ckpt_layout.addWidget(row)

    def _refresh_kpis(self) -> None:
        files = self._find_checkpoint_files()
        n_ckpts = len(list(self._ckpt_dir.glob("*.zip"))) if self._ckpt_dir.is_dir() else 0

        # Try to read DB counts
        try:
            from storage.db import StorageBackend
            db = StorageBackend("data/experiments.db")
            n_snaps = db.count_snapshots()
        except Exception:
            n_snaps = 0

        self._kpi_checkpoints.findChildren(QLabel)[1].setText(str(n_ckpts))
        self._kpi_db_snaps.findChildren(QLabel)[1].setText(f"{n_snaps:,}")

        # Estimate total steps from checkpoint filenames
        total_steps = 0
        for f in (self._ckpt_dir.glob("*.zip") if self._ckpt_dir.is_dir() else []):
            parts = f.stem.split("_")
            for p in parts:
                if p.isdigit():
                    total_steps = max(total_steps, int(p))

        self._kpi_total_steps.findChildren(QLabel)[1].setText(
            f"{total_steps:,}" if total_steps else "—"
        )

        # Status strip
        now = datetime.now().strftime("%H:%M:%S")
        self._status_strip.setText(
            f"✓  Dashboard active  •  Checkpoint dir: {self._ckpt_dir.resolve()}"
            f"  •  Last refresh: {now}"
        )
