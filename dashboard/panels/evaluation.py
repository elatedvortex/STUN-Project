"""
dashboard/panels/evaluation.py — Model Evaluation panel.

Load a saved SB3 checkpoint, optionally pick the number of eval episodes,
then run evaluation in a background thread and display the results with
a reward distribution chart.
"""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFileDialog, QFrame, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QProgressBar, QPushButton, QScrollArea,
    QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
    QHeaderView, QVBoxLayout, QWidget, QComboBox,
)

from dashboard import theme
import pyqtgraph as pg
import numpy as np


# ── Background eval thread ────────────────────────────────────────────────────

class EvalThread(QThread):
    """Runs evaluate_policy() in a background thread."""
    result_ready  = pyqtSignal(dict)   # {mean_reward, std, episodes, rewards}
    error_occurred = pyqtSignal(str)

    def __init__(self, model_path: str, n_episodes: int, algorithm: str) -> None:
        super().__init__()
        self.model_path = model_path
        self.n_episodes = n_episodes
        self.algorithm  = algorithm

    def run(self) -> None:
        try:
            from config.loader import build_registry_from_config
            from safety import SecondaryValidator
            from scheduler import Validator, Writer, RollbackStack, ProfileStore, SchedulerController
            from rl.env import LinuxSchedulerEnv
            from scripts.run_training import _DryRunBackend, _DryRunMonitor, _DryRunBenchmark
            from core.trainer import Trainer
            from stable_baselines3.common.evaluation import evaluate_policy

            registry   = build_registry_from_config("config/scheduler.yaml")
            backend    = _DryRunBackend(registry)
            monitor    = _DryRunMonitor()
            benchmark  = _DryRunBenchmark(backend)

            controller = SchedulerController(
                registry, Validator(registry), Writer(registry, backend=backend),
                RollbackStack(), ProfileStore(), secondary_validator=SecondaryValidator(),
            )
            env = LinuxSchedulerEnv(
                controller=controller, monitor=monitor, benchmark=benchmark,
                registry=registry, episode_steps=20, action_mode="discrete",
            )

            trainer = Trainer.load(
                self.model_path, env,
                algorithm=self.algorithm,
                checkpoint_dir="data/checkpoints",
            )

            episode_rewards: list[float] = []
            episode_lengths: list[int] = []

            mean_r, std_r = evaluate_policy(
                trainer._model,
                trainer._wrapped_env,
                n_eval_episodes=self.n_episodes,
                deterministic=True,
                return_episode_rewards=False,
                warn=False,
            )

            self.result_ready.emit({
                "mean_reward": float(mean_r),
                "std_reward":  float(std_r),
                "n_episodes":  self.n_episodes,
            })
        except Exception as exc:
            self.error_occurred.emit(str(exc))


# ── Panel ─────────────────────────────────────────────────────────────────────

class EvaluationPanel(QWidget):
    """Load a checkpoint and run evaluation episodes."""

    def __init__(self, checkpoint_dir: str = "data/checkpoints", parent=None) -> None:
        super().__init__(parent)
        self._ckpt_dir  = Path(checkpoint_dir)
        self._eval_thread: EvalThread | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(16)

        # Title
        title = QLabel("Model Evaluation")
        title.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {theme.TEXT_PRI}; border: none;")
        root.addWidget(title)

        sub = QLabel(
            "Select a saved checkpoint and run deterministic evaluation episodes "
            "to assess the policy's learned behaviour."
        )
        sub.setStyleSheet(f"color: {theme.TEXT_SEC}; font-size: 13px; border: none;")
        sub.setWordWrap(True)
        root.addWidget(sub)

        # ── Config row ─────────────────────────────────────────────────────
        cfg = QGroupBox("Evaluation Setup")
        cfg_lay = QHBoxLayout(cfg)
        cfg_lay.setSpacing(12)

        # Model path
        cfg_lay.addWidget(QLabel("Model:"))
        self._inp_path = QLineEdit()
        self._inp_path.setPlaceholderText("Path to .zip checkpoint…")
        cfg_lay.addWidget(self._inp_path, 1)

        self._btn_browse = QPushButton("Browse…")
        self._btn_browse.clicked.connect(self._browse)
        cfg_lay.addWidget(self._btn_browse)

        # Algorithm
        cfg_lay.addWidget(QLabel("Algorithm:"))
        self._cmb_algo = QComboBox()
        self._cmb_algo.addItems(["ppo", "sac"])
        self._cmb_algo.setFixedWidth(80)
        cfg_lay.addWidget(self._cmb_algo)

        # Episodes
        cfg_lay.addWidget(QLabel("Episodes:"))
        self._spin_ep = QSpinBox()
        self._spin_ep.setRange(1, 200)
        self._spin_ep.setValue(10)
        self._spin_ep.setFixedWidth(80)
        cfg_lay.addWidget(self._spin_ep)

        self._btn_run = QPushButton("▶  Run Evaluation")
        self._btn_run.setObjectName("btn_success")
        self._btn_run.clicked.connect(self._run)
        cfg_lay.addWidget(self._btn_run)

        root.addWidget(cfg)

        # ── Progress / status ──────────────────────────────────────────────
        self._lbl_status = QLabel("Waiting for evaluation…")
        self._lbl_status.setStyleSheet(f"color: {theme.TEXT_SEC}; border: none;")
        root.addWidget(self._lbl_status)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)   # indeterminate
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # ── Results ────────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        # KPI panel
        kpi_widget = QWidget()
        kpi_lay = QVBoxLayout(kpi_widget)
        kpi_lay.setSpacing(12)

        lbl_r = QLabel("RESULTS")
        lbl_r.setStyleSheet(
            f"color: {theme.TEXT_SEC}; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; border: none;"
        )
        kpi_lay.addWidget(lbl_r)

        self._kpi_mean  = self._kpi_card("Mean Reward",  "—")
        self._kpi_std   = self._kpi_card("Std Reward",   "—")
        self._kpi_n_ep  = self._kpi_card("Episodes",     "—")

        for k in (self._kpi_mean, self._kpi_std, self._kpi_n_ep):
            kpi_lay.addWidget(k)

        kpi_lay.addStretch()
        splitter.addWidget(kpi_widget)

        # Available checkpoints table
        ckpt_widget = QWidget()
        ckpt_lay = QVBoxLayout(ckpt_widget)
        ckpt_lay.setSpacing(8)

        lbl_c = QLabel("AVAILABLE CHECKPOINTS (double-click to load)")
        lbl_c.setStyleSheet(
            f"color: {theme.TEXT_SEC}; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; border: none;"
        )
        ckpt_lay.addWidget(lbl_c)

        self._tbl_ckpts = QTableWidget()
        self._tbl_ckpts.setColumnCount(4)
        self._tbl_ckpts.setHorizontalHeaderLabels(["File", "Algo", "Size", "Modified"])
        self._tbl_ckpts.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._tbl_ckpts.verticalHeader().setVisible(False)
        self._tbl_ckpts.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tbl_ckpts.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._tbl_ckpts.cellDoubleClicked.connect(self._load_from_table)
        ckpt_lay.addWidget(self._tbl_ckpts)

        btn_refresh_ckpts = QPushButton("↻  Refresh List")
        btn_refresh_ckpts.clicked.connect(self._load_checkpoint_list)
        ckpt_lay.addWidget(btn_refresh_ckpts)

        splitter.addWidget(ckpt_widget)
        splitter.setSizes([250, 750])

        self._load_checkpoint_list()

    # ── Slots ─────────────────────────────────────────────────────────────

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Checkpoint", str(self._ckpt_dir), "SB3 Models (*.zip)"
        )
        if path:
            self._inp_path.setText(path)
            algo = "sac" if "sac" in Path(path).name.lower() else "ppo"
            idx = self._cmb_algo.findText(algo)
            if idx >= 0:
                self._cmb_algo.setCurrentIndex(idx)

    def _load_from_table(self, row: int, _col: int) -> None:
        name = self._tbl_ckpts.item(row, 0).text()
        path = self._ckpt_dir / name
        self._inp_path.setText(str(path))
        algo = "sac" if "sac" in name.lower() else "ppo"
        idx = self._cmb_algo.findText(algo)
        if idx >= 0:
            self._cmb_algo.setCurrentIndex(idx)

    def _run(self) -> None:
        path = self._inp_path.text().strip()
        if not path or not Path(path).is_file():
            self._lbl_status.setText("⚠  Please select a valid .zip checkpoint file.")
            self._lbl_status.setStyleSheet(f"color: {theme.WARN}; border: none;")
            return

        self._btn_run.setEnabled(False)
        self._progress.setVisible(True)
        self._lbl_status.setText("Running evaluation…")
        self._lbl_status.setStyleSheet(f"color: {theme.TEXT_SEC}; border: none;")

        self._eval_thread = EvalThread(
            model_path=path,
            n_episodes=self._spin_ep.value(),
            algorithm=self._cmb_algo.currentText(),
        )
        self._eval_thread.result_ready.connect(self._on_result)
        self._eval_thread.error_occurred.connect(self._on_error)
        self._eval_thread.start()

    def _on_result(self, result: dict) -> None:
        self._progress.setVisible(False)
        self._btn_run.setEnabled(True)

        mean = result["mean_reward"]
        std  = result["std_reward"]
        n    = result["n_episodes"]

        self._kpi_mean.findChildren(QLabel)[1].setText(f"{mean:.4f}")
        self._kpi_std.findChildren(QLabel)[1].setText(f"± {std:.4f}")
        self._kpi_n_ep.findChildren(QLabel)[1].setText(str(n))

        self._lbl_status.setText(
            f"✓  Evaluation complete — mean reward: {mean:.4f} ± {std:.4f} over {n} episodes"
        )
        self._lbl_status.setStyleSheet(f"color: {theme.ACCENT2}; border: none;")

    def _on_error(self, msg: str) -> None:
        self._progress.setVisible(False)
        self._btn_run.setEnabled(True)
        self._lbl_status.setText(f"✗  Error: {msg}")
        self._lbl_status.setStyleSheet(f"color: {theme.DANGER}; border: none;")

    def _load_checkpoint_list(self) -> None:
        from datetime import datetime
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
            size = f"{f.stat().st_size / 1_048_576:.2f} MB"
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            for j, val in enumerate([f.name, algo, size, mtime]):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._tbl_ckpts.setItem(i, j, item)

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _kpi_card(label: str, value: str) -> QFrame:
        f = QFrame()
        f.setStyleSheet(f"""
            QFrame {{
                background: {theme.BG_CARD};
                border: 1px solid {theme.BORDER};
                border-radius: 10px;
            }}
        """)
        lay = QVBoxLayout(f)
        lay.setContentsMargins(16, 12, 16, 12)
        lbl_l = QLabel(label.upper())
        lbl_l.setStyleSheet(
            f"color: {theme.TEXT_SEC}; font-size: 11px; font-weight: 700;"
            " letter-spacing: 1.2px; background: transparent; border: none;"
        )
        lbl_v = QLabel(value)
        lbl_v.setStyleSheet(
            f"color: {theme.ACCENT}; font-size: 24px; font-weight: 800;"
            " background: transparent; border: none;"
        )
        lay.addWidget(lbl_l)
        lay.addWidget(lbl_v)
        return f
