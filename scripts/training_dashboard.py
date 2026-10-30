#!/usr/bin/env python3
import sys
import os
import time
from pathlib import Path

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
    QWidget, QProgressBar, QPushButton, QLabel, QFrame
)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QFont, QColor
import pyqtgraph as pg

# Import RL components
from config.loader import build_registry_from_config
from safety import SecondaryValidator, CheckpointManager
from scheduler import Validator, Writer, RollbackStack, ProfileStore, SchedulerController
from rl.env import LinuxSchedulerEnv
from core.trainer import Trainer

# Import dry-run stubs from the run_training script
from scripts.run_training import _DryRunBackend, _DryRunMonitor, _DryRunBenchmark

class TrainingThread(QThread):
    finished_signal = pyqtSignal(str)

    def __init__(self, timesteps: int):
        super().__init__()
        self.timesteps = timesteps
        self.trainer = None
        self.is_running = True

    def run(self):
        registry = build_registry_from_config("config/scheduler.yaml")
        backend = _DryRunBackend(registry)
        monitor = _DryRunMonitor()
        benchmark = _DryRunBenchmark(backend)
        
        controller = SchedulerController(
            registry, Validator(registry), Writer(registry, backend=backend),
            RollbackStack(), ProfileStore(), secondary_validator=SecondaryValidator()
        )
        
        env = LinuxSchedulerEnv(
            controller=controller, monitor=monitor, benchmark=benchmark,
            registry=registry, episode_steps=20, action_mode="discrete"
        )
        
        self.trainer = Trainer(
            env, algorithm="ppo", checkpoint_dir="data/checkpoints",
            n_steps=256, batch_size=64, n_epochs=4
        )
        
        # Start training
        try:
            self.trainer.train(total_timesteps=self.timesteps, checkpoint_freq=5000)
            self.finished_signal.emit("Training Completed Successfully!")
        except Exception as e:
            self.finished_signal.emit(f"Training Stopped: {str(e)}")

class TrainingDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RL Scheduler - Training Dashboard")
        self.resize(900, 600)
        self.setStyleSheet("background-color: #0F111A; color: #E2E8F0;")
        
        self.total_timesteps = 25000
        self.training_thread = None
        
        self._init_ui()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_gui)
        
    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header
        title = QLabel("Reinforcement Learning Training Progress (PPO)")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #3B82F6; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Graph
        self.graph = pg.PlotWidget()
        self.graph.setBackground('#1E293B')
        self.graph.setTitle("Episode Rewards", color="#94A3B8", size="12pt")
        self.graph.setLabel('left', 'Reward')
        self.graph.setLabel('bottom', 'Episodes')
        self.graph.showGrid(x=True, y=True, alpha=0.2)
        self.reward_line = self.graph.plot(pen=pg.mkPen(color='#10B981', width=3))
        layout.addWidget(self.graph)
        
        # Stats Layout
        stats_layout = QHBoxLayout()
        self.lbl_steps = QLabel("Steps: 0 / 0")
        self.lbl_reward = QLabel("Mean Reward: 0.00")
        for lbl in (self.lbl_steps, self.lbl_reward):
            lbl.setFont(QFont("Consolas", 12))
            lbl.setStyleSheet("color: #A78BFA;")
            stats_layout.addWidget(lbl)
        layout.addLayout(stats_layout)
        
        # Progress Bar
        self.progress = QProgressBar()
        self.progress.setMaximum(self.total_timesteps)
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #3B82F6;
                border-radius: 5px;
                text-align: center;
                background-color: #1E293B;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #3B82F6;
                width: 10px;
            }
        """)
        layout.addWidget(self.progress)
        
        # Controls
        controls = QHBoxLayout()
        self.btn_start = QPushButton("▶ Start Training")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #10B981; color: white; border-radius: 4px;
                padding: 10px; font-weight: bold; font-size: 14px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.btn_start.clicked.connect(self.start_training)
        controls.addWidget(self.btn_start)
        layout.addLayout(controls)
        
    def start_training(self):
        self.btn_start.setEnabled(False)
        self.btn_start.setText("Training in Progress...")
        self.btn_start.setStyleSheet("background-color: #94A3B8; color: white; padding: 10px;")
        
        self.training_thread = TrainingThread(self.total_timesteps)
        self.training_thread.finished_signal.connect(self.training_finished)
        self.training_thread.start()
        self.timer.start(500) # Update GUI every 500ms
        
    def update_gui(self):
        if not self.training_thread or not self.training_thread.trainer:
            return
            
        # Access internal SB3 monitor data
        env = self.training_thread.trainer._wrapped_env
        rewards = env.get_episode_rewards()
        steps = self.training_thread.trainer.num_timesteps
        
        # Update progress bar
        self.progress.setValue(steps)
        self.lbl_steps.setText(f"Steps: {steps:,} / {self.total_timesteps:,}")
        
        # Update graph
        if rewards:
            self.reward_line.setData(rewards)
            recent_mean = sum(rewards[-10:]) / min(len(rewards), 10)
            self.lbl_reward.setText(f"Recent Mean Reward: {recent_mean:.2f}")

    def training_finished(self, msg):
        self.timer.stop()
        self.update_gui() # final update
        self.btn_start.setText(msg)
        self.btn_start.setStyleSheet("background-color: #3B82F6; color: white; padding: 10px;")

if __name__ == "__main__":
    app = QApplication(sys.path)
    window = TrainingDashboard()
    window.show()
    sys.exit(app.exec())
