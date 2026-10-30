"""
dashboard/panels/autotuner_panel.py
====================================
Auto-Tuner & Parameter Sweep panel — complete rewrite.

Layout
------
  Top bar   : page title + elapsed clock + DB path indicator
  Tab 1 (Sweep)  :
      Left  : configuration form + start/stop button
      Right : live score plot (trial score vs best-so-far)
              + scrollable trial log table
              + best-params-per-workload result table
  Tab 2 (Agent)  :
      Status card  : current category / workload / top process
      Best score   : fetched from sweep DB
      Apply button : write best params via controller (dry-run toggle)

Worker
------
  SweepWorker runs ParameterSweep in a QThread.
  It wraps _trial() to emit a signal after every trial with:
    (iteration: int, workload: str, score: float,
     is_best: bool, higher_is_better: bool, params: dict)
  This lets the UI plot correctly regardless of score direction.
"""
from __future__ import annotations

import logging
import os
import random
import time
from typing import Any, Dict, List, Optional

import pyqtgraph as pg
from PyQt6.QtCore import QThread, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QProgressBar, QPushButton, QScrollArea, QSizePolicy,
    QSpinBox, QSplitter, QStackedWidget, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from dashboard import theme

logger = logging.getLogger(__name__)

# ── Palette shortcuts ─────────────────────────────────────────────────────────
_C = theme       # alias


# ══════════════════════════════════════════════════════════════════════════════
# Helper widgets
# ══════════════════════════════════════════════════════════════════════════════

def _card(parent=None) -> QFrame:
    f = QFrame(parent)
    f.setStyleSheet(
        f"background:{_C.BG_CARD}; border:1px solid {_C.BORDER}; border-radius:10px;"
    )
    return f


def _label(text="", color=None, size=13, bold=False, parent=None) -> QLabel:
    lbl = QLabel(text, parent)
    css = f"color:{color or _C.TEXT_SEC}; font-size:{size}px; border:none;"
    if bold:
        css += " font-weight:700;"
    lbl.setStyleSheet(css)
    return lbl


def _btn(text, color=_C.ACCENT, w=None, parent=None) -> QPushButton:
    b = QPushButton(text, parent)
    b.setStyleSheet(f"""
        QPushButton {{
            background:{color}; color:#fff; border:none;
            border-radius:7px; padding:8px 18px;
            font-size:13px; font-weight:700;
        }}
        QPushButton:hover   {{ background:{color}cc; }}
        QPushButton:pressed {{ background:{color}88; }}
        QPushButton:disabled{{ background:#333; color:#666; }}
    """)
    if w:
        b.setFixedWidth(w)
    return b


def _progress_bar() -> QProgressBar:
    pb = QProgressBar()
    pb.setRange(0, 100)
    pb.setValue(0)
    pb.setFixedHeight(8)
    pb.setTextVisible(False)
    pb.setStyleSheet(f"""
        QProgressBar        {{ background:{_C.BG_DEEP}; border-radius:4px; border:none; }}
        QProgressBar::chunk {{ background:{_C.ACCENT2}; border-radius:4px; }}
    """)
    return pb


def _table(headers: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setStyleSheet(f"""
        QTableWidget       {{ background:{_C.BG_DEEP}; gridline-color:{_C.BORDER};
                              color:{_C.TEXT_PRI}; border:none; border-radius:8px; }}
        QHeaderView::section {{ background:{_C.BG_CARD}; color:{_C.TEXT_SEC};
                                font-weight:700; font-size:11px; padding:6px 10px;
                                border:none; border-bottom:1px solid {_C.BORDER}; }}
        QTableWidget::item {{ border:none; padding:5px 8px; }}
    """)
    t.setAlternatingRowColors(True)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    t.verticalHeader().setVisible(False)
    return t


class _KpiCard(QFrame):
    """Small stat card: label on top, big value below."""

    def __init__(self, label: str, value: str = "—", parent=None):
        super().__init__(parent)
        self.setFixedWidth(140)
        self.setStyleSheet(
            f"background:{_C.BG_CARD}; border:1px solid {_C.BORDER}; border-radius:10px;"
        )
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(2)
        self._lbl_title = _label(label, color=_C.TEXT_SEC, size=10, bold=True)
        self._lbl_value = _label(value, color=_C.TEXT_PRI, size=22, bold=True)
        v.addWidget(self._lbl_title)
        v.addWidget(self._lbl_value)

    def set_value(self, text: str, color: str = _C.TEXT_PRI):
        self._lbl_value.setText(text)
        self._lbl_value.setStyleSheet(
            f"color:{color}; font-size:22px; font-weight:700; border:none;"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Background worker
# ══════════════════════════════════════════════════════════════════════════════

class SweepWorker(QThread):
    """Runs ParameterSweep in a background thread, emitting one signal per trial.

    Signals
    -------
    trial_done(iter, workload, score, is_best, higher_is_better, params)
    epoch_done(pass_no, workload, best_score)
    log_line(msg)
    sweep_done(summaries_list)
    sweep_error(error_str)
    """

    trial_done  = pyqtSignal(int, str, float, bool, bool, dict)
    epoch_done  = pyqtSignal(int, str, float)
    log_line    = pyqtSignal(str)
    sweep_done  = pyqtSignal(list)
    sweep_error = pyqtSignal(str)

    def __init__(
        self,
        workload: str,
        steps: int,
        strategy: str,
        dry_run: bool,
        db_path: str,
        repeat: int = 1,
    ):
        super().__init__()
        self.workload  = workload
        self.steps     = steps
        self.strategy  = strategy
        self.dry_run   = dry_run
        self.db_path   = db_path
        self.repeat    = repeat
        self._stop     = False

    def stop(self):
        self._stop = True

    # ------------------------------------------------------------------
    def run(self):
        try:
            self._run_inner()
        except Exception as exc:
            logger.exception("SweepWorker error")
            self.sweep_error.emit(str(exc))

    def _run_inner(self):
        from config.loader        import build_registry_from_config
        from storage.db           import StorageBackend
        from benchmarks.sweep     import ParameterSweep
        from benchmarks.types     import BenchmarkResult
        from scheduler.controller import SchedulerController
        from scheduler.validator  import Validator
        from scheduler.writer     import Writer
        from scheduler.rollback   import RollbackStack
        from scheduler.profile    import ProfileStore
        from safety.validator     import SecondaryValidator
        from workload.categories  import CATEGORY_TO_BENCHMARK_TYPE

        self.log_line.emit("Loading parameter registry…")
        registry = build_registry_from_config()
        storage  = StorageBackend(self.db_path)

        # ── backends ──────────────────────────────────────────────────
        if self.dry_run:
            class _DryBackend:
                def __init__(self, reg):
                    self._state = {p.path: str(p.type(0)) for p in reg.get_all()}
                def write(self, path, val): self._state[path] = str(val)
                def read(self, path):       return self._state.get(path, "0")

            class _DryBench:
                def __init__(self, wt):
                    self.name = f"dry-{wt}"
                    self.workload_type = wt
                def run(self, **kw):
                    score = 80.0 + random.uniform(0.0, 40.0)
                    return BenchmarkResult(
                        self.name, self.workload_type,
                        True, score, True,
                        {"score": score, "latency_ms": round(random.uniform(1, 50), 2)},
                    )

            dry_bk  = _DryBackend(registry)
            writer  = Writer(registry, backend=dry_bk)
            factory = lambda wt: _DryBench(wt)
        else:
            from benchmarks.adapters import (
                StressNgAdapter, SysbenchAdapter, HackbenchAdapter,
                CyclictestAdapter, FioAdapter, GamingAdapter,
            )
            _adapter_map = {
                "cpu":         StressNgAdapter,
                "memory":      SysbenchAdapter,
                "mixed":       HackbenchAdapter,
                "interactive": CyclictestAdapter,
                "io":          FioAdapter,
                "gaming":      GamingAdapter,
            }
            writer  = Writer(registry)
            factory = lambda wt: _adapter_map.get(wt, StressNgAdapter)()

        controller = SchedulerController(
            registry,
            Validator(registry),
            writer,
            RollbackStack(),
            ProfileStore(),
            secondary_validator=SecondaryValidator(),
            storage_backend=storage,
        )

        all_wts = list(dict.fromkeys(CATEGORY_TO_BENCHMARK_TYPE.values()))
        targets = [self.workload] if self.workload in all_wts else all_wts

        # ── instrument ParameterSweep ─────────────────────────────────
        global_iter = 0
        global_best: Dict[str, float] = {}
        worker_self = self   # capture for nested class

        class _InstrumentedSweep(ParameterSweep):
            def _trial(inner_self, params, workload_type, tag):
                nonlocal global_iter
                if worker_self._stop:
                    from benchmarks.types import BenchmarkResult
                    return BenchmarkResult("stopped", workload_type, False, 0.0, True)

                result = super()._trial(params, workload_type, tag)
                global_iter += 1

                is_best = False
                if result.success and result.score != 0.0:
                    prev = global_best.get(workload_type)
                    better = (
                        prev is None
                        or (result.score_is_higher_better and result.score > prev)
                        or (not result.score_is_higher_better and result.score < prev)
                    )
                    if better:
                        global_best[workload_type] = result.score
                        is_best = True

                worker_self.trial_done.emit(
                    global_iter,
                    workload_type,
                    result.score,
                    is_best,
                    result.score_is_higher_better,
                    dict(params),
                )
                return result

        # ── sweep passes ──────────────────────────────────────────────
        summaries = []
        for pass_no in range(self.repeat):
            if self._stop:
                break
            for wt in targets:
                if self._stop:
                    break
                self.log_line.emit(
                    f"[pass {pass_no+1}/{self.repeat}]  workload={wt!r}"
                    f"  strategy={self.strategy}  steps={self.steps}"
                )
                sweep = _InstrumentedSweep(
                    registry=registry,
                    controller=controller,
                    storage=storage,
                    benchmark_factory=factory,
                    steps_per_param=self.steps,
                    strategy=self.strategy,
                    dry_run=self.dry_run,
                )
                est = sweep.estimate_run_count()
                self.log_line.emit(
                    f"[pass {pass_no+1}/{self.repeat}]  estimated trials: {est[self.strategy]}"
                )
                summary = sweep.run(wt)
                summaries.append(summary)
                self.epoch_done.emit(pass_no + 1, wt, summary.best_score)
                self.log_line.emit(
                    f"[pass {pass_no+1}/{self.repeat}]  ✓ done"
                    f"  trials={summary.total_runs}  best={summary.best_score:.4f}"
                )

        self.sweep_done.emit(summaries)


# ══════════════════════════════════════════════════════════════════════════════
# Main panel widget
# ══════════════════════════════════════════════════════════════════════════════

class AutoTunerPanel(QWidget):
    """Auto-Tuner & Parameter Sweep — tabbed MLOps panel."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # ── runtime state ─────────────────────────────────────────────
        self._sweep_worker: Optional[SweepWorker] = None
        self._agent_running = False
        self._db_path = "data/sweep.db"

        # per-workload score history: workload -> (iters, scores, bests, higher_is_better)
        self._history: Dict[str, Dict] = {}
        self._active_workload = ""        # workload currently plotted
        self._total_trials  = 0
        self._current_best: Optional[float] = None
        self._hib = True                  # higher_is_better for active workload
        self._start_time = 0.0

        self._setup_ui()

        # agent polling timer
        self._agent_timer = QTimer(self)
        self._agent_timer.setInterval(5000)
        self._agent_timer.timeout.connect(self._agent_tick)

        # elapsed timer
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._update_elapsed)

        self.refresh_results_table()

    # ══════════════════════════════════════════════════════════════════
    # UI construction
    # ══════════════════════════════════════════════════════════════════

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # ── Page header ───────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = _label("⚡  Auto-Tuner & Parameter Sweep", color=_C.TEXT_PRI, size=19, bold=True)
        hdr.addWidget(title)
        hdr.addStretch()
        self._lbl_db = _label(f"DB: {self._db_path}", color=_C.TEXT_DIM, size=11)
        self._lbl_elapsed = _label("Elapsed: —", color=_C.TEXT_SEC, size=12)
        hdr.addWidget(self._lbl_db)
        hdr.addSpacing(16)
        hdr.addWidget(self._lbl_elapsed)
        root.addLayout(hdr)

        sub = _label(
            "Brute-force kernel sched parameter optimisation across workloads.  "
            "Each trial applies a candidate param set, benchmarks it, records the score, "
            "and persists the best config to SQLite for the Live Tuning Agent.",
            color=_C.TEXT_SEC, size=12,
        )
        sub.setWordWrap(True)
        root.addWidget(sub)

        # ── Tabs ──────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane  {{ background:{_C.BG_CARD}; border:1px solid {_C.BORDER};
                                 border-radius:10px; margin-top:-1px; }}
            QTabBar::tab      {{ background:{_C.BG_DEEP}; color:{_C.TEXT_SEC};
                                 padding:10px 24px; font-weight:600; font-size:13px;
                                 border-top-left-radius:8px; border-top-right-radius:8px;
                                 margin-right:3px; }}
            QTabBar::tab:selected   {{ background:{_C.BG_CARD}; color:{_C.TEXT_PRI};
                                       border-bottom:2px solid {_C.ACCENT}; }}
            QTabBar::tab:hover:!selected {{ background:{_C.BG_HOVER}; color:{_C.TEXT_PRI}; }}
        """)
        self._tabs.addTab(self._build_sweep_tab(), "🔍  Parameter Sweep")
        self._tabs.addTab(self._build_agent_tab(), "🤖  Live Agent")
        root.addWidget(self._tabs, 1)

    # ── Sweep tab ─────────────────────────────────────────────────────

    def _build_sweep_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        # Top row: KPIs + plot
        top = QHBoxLayout()
        top.setSpacing(12)

        # KPI cards
        kpi_col = QVBoxLayout()
        kpi_col.setSpacing(8)
        self._kpi_iter  = _KpiCard("TRIALS", "0")
        self._kpi_best  = _KpiCard("BEST SCORE", "—")
        self._kpi_wl    = _KpiCard("WORKLOAD", "—")
        self._kpi_pass  = _KpiCard("PASS", "—/—")
        for k in (self._kpi_iter, self._kpi_best, self._kpi_wl, self._kpi_pass):
            kpi_col.addWidget(k)
        kpi_col.addStretch()
        top.addLayout(kpi_col)

        # Live score plot
        pg.setConfigOptions(antialias=True, background=_C.BG_CARD)
        self._plot = pg.PlotWidget()
        self._plot.setLabel("left",   "Score")
        self._plot.setLabel("bottom", "Trial #")
        self._plot.showGrid(x=True, y=True, alpha=0.12)
        self._plot.setBackground(_C.BG_CARD)
        self._plot.getAxis("left").setTextPen(_C.TEXT_SEC)
        self._plot.getAxis("bottom").setTextPen(_C.TEXT_SEC)
        legend = self._plot.addLegend(offset=(10, 10))
        self._curve_score = self._plot.plot(
            pen=pg.mkPen(_C.ACCENT, width=1.5), name="Trial score"
        )
        self._curve_best  = self._plot.plot(
            pen=pg.mkPen(_C.ACCENT2, width=2.5,
                         style=Qt.PenStyle.DashLine), name="Best so far"
        )
        self._plot.setMinimumHeight(220)
        top.addWidget(self._plot, 1)
        v.addLayout(top)

        # Progress row
        prog_row = QHBoxLayout()
        self._lbl_status = _label("Ready.", color=_C.TEXT_SEC, size=12)
        prog_row.addWidget(self._lbl_status, 1)
        self._progress = _progress_bar()
        prog_row.addWidget(self._progress, 2)
        v.addLayout(prog_row)

        # Bottom splitter: config | log table + results table
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(5)
        splitter.setStyleSheet(f"QSplitter::handle {{ background:{_C.BORDER}; }}")

        # LEFT: config card
        cfg_card = _card()
        cfg_v = QVBoxLayout(cfg_card)
        cfg_v.setContentsMargins(14, 14, 14, 14)
        cfg_v.setSpacing(10)
        cfg_v.addWidget(_label("Configuration", color=_C.ACCENT2, size=13, bold=True))

        def _row(label_text, widget):
            h = QHBoxLayout()
            lbl = _label(label_text, color=_C.TEXT_SEC, size=12)
            lbl.setFixedWidth(100)
            h.addWidget(lbl)
            h.addWidget(widget, 1)
            cfg_v.addLayout(h)

        self._cmb_workload = QComboBox()
        self._cmb_workload.addItems([
            "All Workloads", "cpu", "memory", "mixed", "interactive", "gaming", "io"
        ])
        _row("Workload:", self._cmb_workload)

        self._cmb_strategy = QComboBox()
        self._cmb_strategy.addItems(["coordinate", "cartesian"])
        _row("Strategy:", self._cmb_strategy)

        self._spn_steps = QSpinBox()
        self._spn_steps.setRange(2, 50)
        self._spn_steps.setValue(5)
        self._spn_steps.setToolTip("Number of candidate values per parameter")
        _row("Steps/param:", self._spn_steps)

        self._spn_repeat = QSpinBox()
        self._spn_repeat.setRange(1, 20)
        self._spn_repeat.setValue(1)
        self._spn_repeat.setToolTip("Number of full sweep passes")
        _row("Passes:", self._spn_repeat)

        self._chk_dry = QCheckBox("Dry-run  (simulated scores, no sysctl writes)")
        self._chk_dry.setChecked(True)
        self._chk_dry.setStyleSheet(f"color:{_C.TEXT_SEC}; font-size:12px;")
        cfg_v.addWidget(self._chk_dry)

        cfg_v.addSpacing(6)
        self._btn_sweep = _btn("▶  Start Sweep", color=_C.ACCENT2, w=190)
        self._btn_sweep.clicked.connect(self._toggle_sweep)
        cfg_v.addWidget(self._btn_sweep)

        cfg_v.addStretch()
        splitter.addWidget(cfg_card)

        # RIGHT: log + results (stacked vertically)
        right_w = QWidget()
        right_v = QVBoxLayout(right_w)
        right_v.setContentsMargins(6, 0, 0, 0)
        right_v.setSpacing(8)

        # Trial log table
        right_v.addWidget(_label("Trial Log", color=_C.TEXT_PRI, size=12, bold=True))
        self._tbl_log = _table(["#", "Workload", "Score", "Best?", "Params"])
        self._tbl_log.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        for col in range(4):
            self._tbl_log.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents)
        right_v.addWidget(self._tbl_log, 3)

        # Results table
        res_hdr = QHBoxLayout()
        res_hdr.addWidget(_label("Best per Workload", color=_C.TEXT_PRI, size=12, bold=True))
        res_hdr.addStretch()
        btn_ref = QPushButton("⟳  Refresh")
        btn_ref.setFixedWidth(90)
        btn_ref.setStyleSheet(
            f"background:transparent; color:{_C.TEXT_SEC}; border:1px solid {_C.BORDER};"
            f" border-radius:6px; padding:4px 8px; font-size:12px;"
        )
        btn_ref.clicked.connect(self.refresh_results_table)
        res_hdr.addWidget(btn_ref)
        right_v.addLayout(res_hdr)

        self._tbl_results = _table(["Workload", "Best Score", "Direction", "Params", "Timestamp"])
        self._tbl_results.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for col in (0, 1, 2, 4):
            self._tbl_results.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents)
        right_v.addWidget(self._tbl_results, 2)

        splitter.addWidget(right_w)
        splitter.setSizes([240, 900])
        v.addWidget(splitter, 1)

        return w

    # ── Agent tab ─────────────────────────────────────────────────────

    def _build_agent_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(14)

        desc = _label(
            "The Live Tuning Agent polls the running system every few seconds, detects the dominant "
            "workload category, and looks up the best scheduler parameters from the sweep database.  "
            "Run a sweep first to populate the database.",
            color=_C.TEXT_SEC, size=12,
        )
        desc.setWordWrap(True)
        v.addWidget(desc)

        # Status card
        status_card = _card()
        sv = QVBoxLayout(status_card)
        sv.setContentsMargins(16, 14, 16, 14)
        sv.setSpacing(8)
        sv.addWidget(_label("System Status", color=_C.ACCENT, size=13, bold=True))

        grid = QHBoxLayout()
        self._agent_badge = QLabel("● STOPPED")
        self._agent_badge.setStyleSheet(
            f"color:{_C.TEXT_SEC}; font-weight:700; background:{_C.BORDER};"
            f" border-radius:6px; padding:3px 12px; font-size:12px;"
        )
        grid.addWidget(self._agent_badge)
        grid.addStretch()
        sv.addLayout(grid)

        self._lbl_cat   = _label("Category:    —", color=_C.TEXT_PRI, size=13)
        self._lbl_wl    = _label("Workload:    —", color=_C.TEXT_PRI, size=13)
        self._lbl_proc  = _label("Top Process: —", color=_C.TEXT_SEC, size=12)
        self._lbl_score = _label("Best Known:  —", color=_C.ACCENT2, size=13, bold=True)
        self._lbl_apply = _label("", color=_C.TEXT_SEC, size=12)
        for lbl in (self._lbl_cat, self._lbl_wl, self._lbl_proc,
                    self._lbl_score, self._lbl_apply):
            sv.addWidget(lbl)

        v.addWidget(status_card)

        # Agent controls card
        ctrl_card = _card()
        cv = QVBoxLayout(ctrl_card)
        cv.setContentsMargins(16, 14, 16, 14)
        cv.setSpacing(10)
        cv.addWidget(_label("Agent Controls", color=_C.ACCENT2, size=13, bold=True))

        self._chk_agent_dry = QCheckBox("Dry-run  (classify & report only, no sysctl writes)")
        self._chk_agent_dry.setChecked(True)
        self._chk_agent_dry.setStyleSheet(f"color:{_C.TEXT_SEC}; font-size:12px;")
        cv.addWidget(self._chk_agent_dry)

        btn_row = QHBoxLayout()
        self._btn_agent = _btn("▶  Start Agent", color=_C.ACCENT)
        self._btn_agent.clicked.connect(self._toggle_agent)
        btn_row.addWidget(self._btn_agent)
        btn_row.addStretch()
        cv.addLayout(btn_row)

        v.addWidget(ctrl_card)
        v.addStretch()
        return w

    # ══════════════════════════════════════════════════════════════════
    # Sweep control
    # ══════════════════════════════════════════════════════════════════

    def _toggle_sweep(self):
        if self._sweep_worker and self._sweep_worker.isRunning():
            self._sweep_worker.stop()
            self._btn_sweep.setText("▶  Start Sweep")
            self._btn_sweep.setStyleSheet(
                f"background:{_C.ACCENT2}; color:#fff; border:none; border-radius:7px;"
                f" padding:8px 18px; font-size:13px; font-weight:700;"
            )
            self._elapsed_timer.stop()
            self._lbl_status.setText("Stopped by user.")
            return

        # Reset state
        self._history.clear()
        self._total_trials  = 0
        self._current_best  = None
        self._hib           = True
        self._start_time    = time.monotonic()
        self._tbl_log.setRowCount(0)
        self._curve_score.setData([], [])
        self._curve_best.setData([], [])
        self._progress.setValue(0)
        self._kpi_iter.set_value("0")
        self._kpi_best.set_value("—")
        self._kpi_wl.set_value("—")
        self._kpi_pass.set_value("—/—")

        workload = self._cmb_workload.currentText()
        if workload == "All Workloads":
            workload = "all"

        self._sweep_worker = SweepWorker(
            workload      = workload,
            steps         = self._spn_steps.value(),
            strategy      = self._cmb_strategy.currentText(),
            dry_run       = self._chk_dry.isChecked(),
            db_path       = self._db_path,
            repeat        = self._spn_repeat.value(),
        )
        self._sweep_worker.trial_done.connect(self._on_trial)
        self._sweep_worker.epoch_done.connect(self._on_epoch)
        self._sweep_worker.log_line.connect(self._on_log)
        self._sweep_worker.sweep_done.connect(self._on_sweep_done)
        self._sweep_worker.sweep_error.connect(self._on_sweep_error)
        self._sweep_worker.start()

        self._btn_sweep.setText("⏹  Stop")
        self._btn_sweep.setStyleSheet(
            f"background:{_C.DANGER}; color:#fff; border:none; border-radius:7px;"
            f" padding:8px 18px; font-size:13px; font-weight:700;"
        )
        self._elapsed_timer.start()
        self._lbl_status.setText("Sweep running…")

    # ── Sweep signal handlers ──────────────────────────────────────────

    def _on_trial(
        self,
        iteration: int,
        workload: str,
        score: float,
        is_best: bool,
        higher_is_better: bool,
        params: dict,
    ):
        self._total_trials = iteration

        # ── per-workload history ───────────────────────────────────────
        if workload not in self._history:
            self._history[workload] = {
                "iters": [], "scores": [], "bests": [],
                "hib": higher_is_better,
            }
        h = self._history[workload]
        h["iters"].append(iteration)
        h["scores"].append(score)

        if not h["bests"]:
            h["bests"].append(score)
        else:
            prev = h["bests"][-1]
            if higher_is_better:
                h["bests"].append(max(score, prev))
            else:
                h["bests"].append(min(score, prev))

        # ── update active workload best ────────────────────────────────
        if is_best or self._active_workload != workload:
            self._active_workload = workload
            self._hib = higher_is_better

        if is_best:
            self._current_best = score

        # ── refresh plot (show active workload) ────────────────────────
        ah = self._history.get(self._active_workload)
        if ah:
            xs = ah["iters"]
            ys = ah["scores"]
            yb = ah["bests"]
            n = len(xs)
            if n > 500:
                step = max(1, n // 250)
                xs, ys, yb = xs[::step], ys[::step], yb[::step]
            self._curve_score.setData(list(xs), list(ys))
            self._curve_best.setData(list(xs), list(yb))

        # ── KPIs ───────────────────────────────────────────────────────
        self._kpi_iter.set_value(str(iteration))
        self._kpi_wl.set_value(workload, color=_C.ACCENT)
        if self._current_best is not None:
            self._kpi_best.set_value(f"{self._current_best:.2f}", color=_C.ACCENT2)

        # ── trial log row ──────────────────────────────────────────────
        row = self._tbl_log.rowCount()
        self._tbl_log.insertRow(row)

        param_str = ", ".join(
            f"{k.split('.')[-1]}={v}" for k, v in list(params.items())[:3]
        ) or "—"
        score_str = f"{score:.4f}" if score != 0.0 else "0 (no output)"

        items = [
            QTableWidgetItem(str(iteration)),
            QTableWidgetItem(workload),
            QTableWidgetItem(score_str),
            QTableWidgetItem("★" if is_best else ""),
            QTableWidgetItem(param_str),
        ]
        for col, item in enumerate(items):
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if col < 4 else Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            if col == 3 and is_best:
                item.setForeground(QColor(_C.ACCENT2))
                item.setFont(QFont("Inter", 12, QFont.Weight.Bold))
            elif col == 2 and score == 0.0:
                item.setForeground(QColor(_C.DANGER))
            self._tbl_log.setItem(row, col, item)

        self._tbl_log.scrollToBottom()

        # ── progress estimate ──────────────────────────────────────────
        from workload.categories import CATEGORY_TO_BENCHMARK_TYPE
        n_wl = len(set(CATEGORY_TO_BENCHMARK_TYPE.values()))
        est  = max(1, self._spn_steps.value() * n_wl * self._spn_repeat.value())
        self._progress.setValue(min(99, int(100 * iteration / est)))

    def _on_epoch(self, pass_no: int, workload: str, best_score: float):
        self._kpi_pass.set_value(f"{pass_no}/{self._spn_repeat.value()}")
        self.refresh_results_table()

    def _on_log(self, msg: str):
        self._lbl_status.setText(msg)

    def _on_sweep_done(self, summaries):
        self._elapsed_timer.stop()
        self._progress.setValue(100)
        n = len(summaries)
        best_str = f"{self._current_best:.4f}" if self._current_best is not None else "—"
        self._lbl_status.setText(
            f"✓ Sweep complete — {n} workload(s), {self._total_trials} trials, best: {best_str}"
        )
        self._btn_sweep.setText("▶  Start Sweep")
        self._btn_sweep.setStyleSheet(
            f"background:{_C.ACCENT2}; color:#fff; border:none; border-radius:7px;"
            f" padding:8px 18px; font-size:13px; font-weight:700;"
        )
        self.refresh_results_table()

    def _on_sweep_error(self, err: str):
        self._elapsed_timer.stop()
        self._lbl_status.setText(f"✗ Error: {err}")
        self._btn_sweep.setText("▶  Start Sweep")
        self._btn_sweep.setStyleSheet(
            f"background:{_C.ACCENT2}; color:#fff; border:none; border-radius:7px;"
            f" padding:8px 18px; font-size:13px; font-weight:700;"
        )

    def _update_elapsed(self):
        secs = int(time.monotonic() - self._start_time)
        m, s = divmod(secs, 60)
        self._lbl_elapsed.setText(f"Elapsed: {m:02d}:{s:02d}")

    # ── Results table ──────────────────────────────────────────────────

    def refresh_results_table(self):
        if not os.path.exists(self._db_path):
            self._tbl_results.setRowCount(0)
            return
        try:
            from storage.db import StorageBackend
            db  = StorageBackend(self._db_path)
            wts = db.list_sweep_workload_types()
            self._tbl_results.setRowCount(len(wts))
            for row, wt in enumerate(wts):
                best = db.best_params_for_workload(wt)
                if not best:
                    continue
                direction = "↑ higher" if best["score_is_higher_better"] else "↓ lower"
                params_str = ", ".join(
                    f"{k.split('.')[-1]}={v}"
                    for k, v in best["sched_params"].items()
                )
                score_item = QTableWidgetItem(f"{best['score']:.4f}")
                score_item.setForeground(QColor(_C.ACCENT2))
                score_item.setFont(QFont("Inter", 12, QFont.Weight.Bold))
                self._tbl_results.setItem(row, 0, QTableWidgetItem(wt))
                self._tbl_results.setItem(row, 1, score_item)
                self._tbl_results.setItem(row, 2, QTableWidgetItem(direction))
                self._tbl_results.setItem(row, 3, QTableWidgetItem(params_str or "—"))
                self._tbl_results.setItem(row, 4, QTableWidgetItem(
                    str(best.get("timestamp", "—"))[:19]
                ))
        except Exception:
            logger.exception("refresh_results_table error")

    # ══════════════════════════════════════════════════════════════════
    # Agent tab
    # ══════════════════════════════════════════════════════════════════

    def _toggle_agent(self):
        if self._agent_running:
            self._agent_running = False
            self._agent_timer.stop()
            self._agent_badge.setText("● STOPPED")
            self._agent_badge.setStyleSheet(
                f"color:{_C.TEXT_SEC}; font-weight:700; background:{_C.BORDER};"
                f" border-radius:6px; padding:3px 12px; font-size:12px;"
            )
            self._btn_agent.setText("▶  Start Agent")
            self._btn_agent.setStyleSheet(
                f"background:{_C.ACCENT}; color:#fff; border:none; border-radius:7px;"
                f" padding:8px 18px; font-size:13px; font-weight:700;"
            )
        else:
            self._agent_running = True
            dry = self._chk_agent_dry.isChecked()
            label = "⏸  DRY-RUN" if dry else "●  RUNNING"
            color = _C.WARN if dry else _C.ACCENT2
            self._agent_badge.setText(label)
            self._agent_badge.setStyleSheet(
                f"color:{color}; font-weight:700; background:{color}22;"
                f" border:1px solid {color}; border-radius:6px; padding:3px 12px; font-size:12px;"
            )
            self._btn_agent.setText("⏹  Stop Agent")
            self._btn_agent.setStyleSheet(
                f"background:{_C.DANGER}; color:#fff; border:none; border-radius:7px;"
                f" padding:8px 18px; font-size:13px; font-weight:700;"
            )
            self._agent_timer.start()
            self._agent_tick()   # immediate first tick

    def _agent_tick(self):
        if not self._agent_running:
            return
        try:
            from monitor.collector           import Monitor
            from workload.classifier         import ProcessClassifier
            from workload.categories         import CATEGORY_TO_BENCHMARK_TYPE
            from storage.db                  import StorageBackend

            snap = Monitor().read_snapshot()
            fp   = ProcessClassifier().fingerprint(snap)
            cat  = fp.primary_category
            wt   = CATEGORY_TO_BENCHMARK_TYPE.get(cat, "mixed")
            top  = fp.top_processes[0][0] if fp.top_processes else "(none)"

            self._lbl_cat.setText(f"Category:    {cat}")
            self._lbl_wl.setText(f"Workload:    {wt}")
            self._lbl_proc.setText(f"Top Process: {top}")

            if os.path.exists(self._db_path):
                db   = StorageBackend(self._db_path)
                best = db.best_params_for_workload(wt)
                if best and best.get("sched_params"):
                    self._lbl_score.setText(
                        f"Best Known:  {best['score']:.4f}  "
                        f"({'↑' if best['score_is_higher_better'] else '↓'})"
                    )
                    # optionally apply (non-dry-run)
                    if not self._chk_agent_dry.isChecked():
                        self._apply_best(best, cat, wt)
                    else:
                        self._lbl_apply.setText("(dry-run — not applied)")
                else:
                    self._lbl_score.setText("Best Known:  no sweep data yet — run a sweep first")
                    self._lbl_apply.setText("")
            else:
                self._lbl_score.setText("Best Known:  sweep DB not found — run a sweep first")
                self._lbl_apply.setText("")
        except Exception:
            logger.exception("agent tick error")

    def _apply_best(self, best: dict, category: str, workload_type: str):
        """Apply best params through the controller (non-dry-run agent mode)."""
        try:
            from config.loader        import build_registry_from_config
            from scheduler.controller import SchedulerController
            from scheduler.validator  import Validator
            from scheduler.writer     import Writer
            from scheduler.rollback   import RollbackStack
            from scheduler.profile    import ProfileStore
            from safety.validator     import SecondaryValidator
            from storage.db           import StorageBackend

            registry = build_registry_from_config()

            # Map sysctl paths -> registry names
            params: Dict[str, Any] = {}
            for meta in registry.get_all():
                if meta.path in best["sched_params"]:
                    try:
                        params[meta.name] = meta.type(best["sched_params"][meta.path])
                    except Exception:
                        continue

            if not params:
                self._lbl_apply.setText("⚠ No registry params matched sweep result")
                return

            storage = StorageBackend(self._db_path)
            ctrl = SchedulerController(
                registry, Validator(registry), Writer(registry),
                RollbackStack(), ProfileStore(),
                secondary_validator=SecondaryValidator(),
                storage_backend=storage,
            )
            ctrl.apply_parameters(params)
            self._lbl_apply.setText(
                f"✓ Applied {len(params)} param(s) for {category}/{workload_type}"
            )
        except Exception as exc:
            self._lbl_apply.setText(f"✗ Apply failed: {exc}")
            logger.exception("agent _apply_best error")
