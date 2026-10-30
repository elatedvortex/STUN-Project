"""
dashboard/panels/new_training.py — New Experiment configuration panel.

Collects experiment name, algorithm, training budget, and hyperparameters,
then emits a launch_requested signal so the main window can hand the config
to LiveTrainingPanel and navigate there.
"""
from __future__ import annotations
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)
from dashboard import theme
from dashboard.panels.live_training import TrainingConfig


class NewTrainingPanel(QWidget):
    """Configure a new RL training run and launch it."""

    launch_requested = pyqtSignal(object)   # emits TrainingConfig

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        title = QLabel("New Training Configuration")
        title.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {theme.TEXT_PRI}; border: none;")
        main_layout.addWidget(title)

        sub = QLabel(
            "Configure your experiment, then click Launch to start training and switch to "
            "the Live Training monitor automatically."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {theme.TEXT_SEC}; font-size: 13px; border: none;")
        main_layout.addWidget(sub)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(16)

        # ── Experiment Meta ─────────────────────────────────────────────────
        meta_group = QGroupBox("Experiment Details")
        meta_layout = QFormLayout(meta_group)
        meta_layout.setSpacing(10)

        self.inp_name    = QLineEdit("Scheduler-PPO-v1")
        self.inp_desc    = QLineEdit("Initial benchmark run on generic workload.")
        self.inp_out_dir = QLineEdit("data/checkpoints")
        for w in (self.inp_name, self.inp_desc, self.inp_out_dir):
            w.setPlaceholderText(w.text())

        meta_layout.addRow("Experiment Name:", self.inp_name)
        meta_layout.addRow("Description:",     self.inp_desc)
        meta_layout.addRow("Output Directory:", self.inp_out_dir)
        scroll_layout.addWidget(meta_group)

        # ── Algorithm & Environment ─────────────────────────────────────────
        env_group = QGroupBox("Algorithm & Environment")
        env_layout = QFormLayout(env_group)
        env_layout.setSpacing(10)

        self.cmb_algo = QComboBox()
        self.cmb_algo.addItems(["PPO (Proximal Policy Optimization)", "SAC (Soft Actor-Critic)"])

        self.cmb_device = QComboBox()
        self.cmb_device.addItems(["Auto", "CPU", "CUDA"])

        self.spin_seed = QSpinBox()
        self.spin_seed.setRange(0, 999_999)
        self.spin_seed.setValue(42)

        env_layout.addRow("Algorithm:",       self.cmb_algo)
        env_layout.addRow("Device:",          self.cmb_device)
        env_layout.addRow("Random Seed:",     self.spin_seed)
        scroll_layout.addWidget(env_group)

        # ── Training Budget ─────────────────────────────────────────────────
        budget_group = QGroupBox("Training Budget")
        budget_layout = QFormLayout(budget_group)
        budget_layout.setSpacing(10)

        self.spin_timesteps = QSpinBox()
        self.spin_timesteps.setRange(1_000, 100_000_000)
        self.spin_timesteps.setSingleStep(10_000)
        self.spin_timesteps.setValue(50_000)

        self.spin_ep_length = QSpinBox()
        self.spin_ep_length.setRange(1, 1_000)
        self.spin_ep_length.setValue(20)

        self.spin_ckpt_freq = QSpinBox()
        self.spin_ckpt_freq.setRange(100, 100_000)
        self.spin_ckpt_freq.setSingleStep(1_000)
        self.spin_ckpt_freq.setValue(5_000)

        budget_layout.addRow("Total Timesteps:",       self.spin_timesteps)
        budget_layout.addRow("Episode Length (steps):", self.spin_ep_length)
        budget_layout.addRow("Checkpoint Frequency:",  self.spin_ckpt_freq)
        scroll_layout.addWidget(budget_group)

        # ── PPO Hyperparameters ─────────────────────────────────────────────
        ppo_group = QGroupBox("PPO Hyperparameters")
        ppo_layout = QFormLayout(ppo_group)
        ppo_layout.setSpacing(10)

        self.ppo_lr      = QDoubleSpinBox(); self.ppo_lr.setDecimals(5); self.ppo_lr.setSingleStep(0.0001); self.ppo_lr.setValue(3e-4)
        self.ppo_nsteps  = QSpinBox();  self.ppo_nsteps.setRange(16, 4096);  self.ppo_nsteps.setValue(256)
        self.ppo_batch   = QSpinBox();  self.ppo_batch.setRange(8, 2048);    self.ppo_batch.setValue(64)
        self.ppo_epochs  = QSpinBox();  self.ppo_epochs.setRange(1, 100);    self.ppo_epochs.setValue(4)
        self.ppo_gamma   = QDoubleSpinBox(); self.ppo_gamma.setDecimals(3); self.ppo_gamma.setSingleStep(0.01); self.ppo_gamma.setValue(0.99)
        self.ppo_ent     = QDoubleSpinBox(); self.ppo_ent.setDecimals(4);   self.ppo_ent.setSingleStep(0.001); self.ppo_ent.setValue(0.0)

        ppo_layout.addRow("Learning Rate:",       self.ppo_lr)
        ppo_layout.addRow("n_steps:",             self.ppo_nsteps)
        ppo_layout.addRow("Batch Size:",          self.ppo_batch)
        ppo_layout.addRow("n_epochs:",            self.ppo_epochs)
        ppo_layout.addRow("Gamma:",               self.ppo_gamma)
        ppo_layout.addRow("Entropy Coefficient:", self.ppo_ent)
        scroll_layout.addWidget(ppo_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, 1)

        # ── Action buttons ──────────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_save = QPushButton("💾  Save Config")
        self.btn_save.clicked.connect(self._save_config)

        self.btn_launch = QPushButton("▶  Launch Training")
        self.btn_launch.setObjectName("btn_success")
        self.btn_launch.clicked.connect(self._launch)

        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_launch)
        main_layout.addLayout(btn_layout)

        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet(f"color: {theme.ACCENT2}; font-size: 12px; border: none;")
        main_layout.addWidget(self._lbl_status)

    # ── Helpers ────────────────────────────────────────────────────────────

    def _build_config(self) -> TrainingConfig:
        algo_text = self.cmb_algo.currentText()
        algo = "sac" if "SAC" in algo_text else "ppo"
        return TrainingConfig(
            experiment_name  = self.inp_name.text().strip() or "experiment",
            algorithm        = algo,
            timesteps        = self.spin_timesteps.value(),
            episode_steps    = self.spin_ep_length.value(),
            checkpoint_dir   = self.inp_out_dir.text().strip() or "data/checkpoints",
            checkpoint_freq  = self.spin_ckpt_freq.value(),
            seed             = self.spin_seed.value(),
            n_steps          = self.ppo_nsteps.value(),
            batch_size       = self.ppo_batch.value(),
            n_epochs         = self.ppo_epochs.value(),
            learning_rate    = self.ppo_lr.value(),
            gamma            = self.ppo_gamma.value(),
            ent_coef         = self.ppo_ent.value(),
        )

    def _save_config(self) -> None:
        self._lbl_status.setText("Configuration saved (in-memory).")

    def _launch(self) -> None:
        cfg = self._build_config()
        self._lbl_status.setText(
            f"Launching {cfg.algorithm.upper()} for {cfg.timesteps:,} steps…"
        )
        self.launch_requested.emit(cfg)
