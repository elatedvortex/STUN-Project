"""
dashboard/panels/live_training.py — Live Training Monitor panel.

Wires the LiveMetricsCallback from core/metrics.py into the Trainer
so that real SB3 metrics are streamed to pyqtgraph charts in the GUI
without blocking the event loop.

Controls: Start · Pause / Resume · Stop
Charts  : Reward curve, Policy Loss, Value Loss, Entropy, FPS
"""
from __future__ import annotations

import time
from typing import Optional

import pyqtgraph as pg
from PyQt6.QtCore import QMutex, QThread, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame, QGroupBox, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QSplitter,
    QTabWidget, QVBoxLayout, QWidget,
)

from dashboard import theme
from core.metrics import LiveMetricsCallback, TrainingStepMetric, TrainingEpisodeMetric


# ── Training configuration dataclass ─────────────────────────────────────────

class TrainingConfig:
    """Bundle of all settings passed from NewTrainingPanel / HyperparametersPanel."""
    def __init__(
        self,
        experiment_name: str = "Scheduler-PPO-v1",
        algorithm: str = "ppo",
        timesteps: int = 50_000,
        episode_steps: int = 20,
        checkpoint_dir: str = "data/checkpoints",
        checkpoint_freq: int = 5_000,
        seed: int = 42,
        # PPO hyperparams
        n_steps: int = 256,
        batch_size: int = 64,
        n_epochs: int = 4,
        learning_rate: float = 3e-4,
        gamma: float = 0.99,
        ent_coef: float = 0.0,
        # SAC hyperparams
        buffer_size: int = 100_000,
        tau: float = 0.005,
    ) -> None:
        self.experiment_name  = experiment_name
        self.algorithm        = algorithm.lower()
        self.timesteps        = timesteps
        self.episode_steps    = episode_steps
        self.checkpoint_dir   = checkpoint_dir
        self.checkpoint_freq  = checkpoint_freq
        self.seed             = seed
        self.n_steps          = n_steps
        self.batch_size       = batch_size
        self.n_epochs         = n_epochs
        self.learning_rate    = learning_rate
        self.gamma            = gamma
        self.ent_coef         = ent_coef
        self.buffer_size      = buffer_size
        self.tau              = tau


# ── Background training thread ────────────────────────────────────────────────

class TrainingThread(QThread):
    finished_signal = pyqtSignal(str)

    def __init__(self, config: TrainingConfig, metrics_cb: LiveMetricsCallback) -> None:
        super().__init__()
        self.config     = config
        self.metrics_cb = metrics_cb
        self.trainer    = None

    def run(self) -> None:
        try:
            from config.loader import build_registry_from_config
            from safety import SecondaryValidator
            from scheduler import (
                Validator, Writer, RollbackStack, ProfileStore, SchedulerController,
            )
            from rl.env import LinuxSchedulerEnv
            from scripts.run_training import _DryRunBackend, _DryRunMonitor, _DryRunBenchmark
            from core.trainer import Trainer

            cfg = self.config
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
                registry=registry, episode_steps=cfg.episode_steps,
                action_mode="discrete" if cfg.algorithm == "ppo" else "continuous",
            )

            algo_kwargs: dict = {"seed": cfg.seed}
            if cfg.algorithm == "ppo":
                algo_kwargs.update(
                    n_steps=cfg.n_steps, batch_size=cfg.batch_size,
                    n_epochs=cfg.n_epochs, learning_rate=cfg.learning_rate,
                    gamma=cfg.gamma, ent_coef=cfg.ent_coef,
                )
            else:  # sac
                algo_kwargs.update(
                    buffer_size=cfg.buffer_size, batch_size=cfg.batch_size,
                    learning_rate=cfg.learning_rate, gamma=cfg.gamma, tau=cfg.tau,
                )

            self.trainer = Trainer(
                env,
                algorithm=cfg.algorithm,
                checkpoint_dir=cfg.checkpoint_dir,
                **algo_kwargs,
            )

            self.metrics_cb.total_timesteps = cfg.timesteps

            self.trainer.train(
                total_timesteps=cfg.timesteps,
                checkpoint_freq=cfg.checkpoint_freq,
                callbacks=[self.metrics_cb],
            )
            self.finished_signal.emit("Training completed successfully.")
        except Exception as exc:
            self.finished_signal.emit(f"Error: {exc}")


# ── Live Training Panel ───────────────────────────────────────────────────────

class LiveTrainingPanel(QWidget):
    """Multi-chart live training monitor with pause/resume/stop controls."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._config: TrainingConfig = TrainingConfig()
        self._thread: Optional[TrainingThread] = None
        self._metrics_cb: Optional[LiveMetricsCallback] = None
        self._mutex = QMutex()

        # Rolling data buffers
        self._steps:        list[float] = []
        self._rewards:      list[float] = []
        self._mean10:       list[float] = []
        self._best:         list[float] = []
        self._policy_loss:  list[float] = []
        self._value_loss:   list[float] = []
        self._entropy:      list[float] = []
        self._fps_buf:      list[float] = []
        self._ep_rewards:   list[float] = []
        self._ep_nums:      list[float] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # ── Header ─────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        self._lbl_title = QLabel("Live Training Monitor")
        self._lbl_title.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        self._lbl_title.setStyleSheet(f"color: {theme.TEXT_PRI}; border: none;")
        hdr.addWidget(self._lbl_title)
        hdr.addStretch()

        self._badge = QLabel("● READY")
        self._badge.setStyleSheet(
            f"color: {theme.TEXT_SEC}; font-size: 12px; font-weight: 700;"
            f" background: {theme.BG_CARD}; border: 1px solid {theme.BORDER};"
            " border-radius: 10px; padding: 3px 12px;"
        )
        hdr.addWidget(self._badge)
        root.addLayout(hdr)

        # ── Progress / status ──────────────────────────────────────────────
        self._lbl_status = QLabel("Configure an experiment in 'New Training' then launch here.")
        self._lbl_status.setStyleSheet(f"color: {theme.TEXT_SEC}; font-size: 13px; border: none;")
        root.addWidget(self._lbl_status)

        self._progress = QProgressBar()
        self._progress.setMinimum(0)
        self._progress.setMaximum(100)
        self._progress.setValue(0)
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {theme.BORDER}; border-radius: 6px; text-align: center;
                background: {theme.BG_DEEP}; color: {theme.TEXT_PRI}; font-weight: 700;
                min-height: 18px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {theme.ACCENT}, stop:1 {theme.ACCENT2});
                border-radius: 5px;
            }}
        """)
        root.addWidget(self._progress)

        # ── KPI cards row ──────────────────────────────────────────────────
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)
        self._kpi_steps   = self._kpi("Steps",        "0",   theme.ACCENT)
        self._kpi_episode = self._kpi("Episodes",     "0",   theme.TEXT_SEC)
        self._kpi_reward  = self._kpi("Last Reward",  "—",   theme.ACCENT2)
        self._kpi_mean10  = self._kpi("Mean (10ep)",  "—",   theme.WARN)
        self._kpi_best    = self._kpi("Best Reward",  "—",   theme.ACCENT2)
        self._kpi_fps     = self._kpi("FPS",          "—",   theme.TEXT_SEC)
        self._kpi_eta     = self._kpi("ETA",          "—",   theme.TEXT_DIM)
        for k in (self._kpi_steps, self._kpi_episode, self._kpi_reward,
                  self._kpi_mean10, self._kpi_best, self._kpi_fps, self._kpi_eta):
            kpi_row.addWidget(k)
        root.addLayout(kpi_row)

        # ── Charts (tabs) ──────────────────────────────────────────────────
        self._tabs = QTabWidget()
        root.addWidget(self._tabs, 1)

        # Tab 1: Reward — legend BEFORE plot() so items auto-register
        rw = QWidget()
        rl = QVBoxLayout(rw)
        rl.setContentsMargins(4, 4, 4, 4)
        self._chart_reward = self._make_plot("Reward vs Steps", "Steps", "Reward")
        _legend_reward = self._chart_reward.addLegend(
            offset=(10, 10),
            labelTextColor=theme.TEXT_PRI,
            labelTextSize="10pt",
        )
        _legend_reward.setParentItem(self._chart_reward.getPlotItem())
        self._line_reward  = self._chart_reward.plot(
            pen=pg.mkPen(theme.ACCENT, width=2.5), name="Step Reward")
        self._line_mean10  = self._chart_reward.plot(
            pen=pg.mkPen(theme.ACCENT2, width=2, style=Qt.PenStyle.DashLine), name="Mean (10 ep)")
        self._line_best    = self._chart_reward.plot(
            pen=pg.mkPen(theme.WARN, width=1.5, style=Qt.PenStyle.DotLine), name="Best")
        rl.addWidget(self._chart_reward)
        self._tabs.addTab(rw, "📈  Reward")

        # Tab 2: Episode Rewards
        ew = QWidget()
        el = QVBoxLayout(ew)
        el.setContentsMargins(4, 4, 4, 4)
        self._chart_ep = self._make_plot("Episode Rewards", "Episode #", "Total Reward")
        _legend_ep = self._chart_ep.addLegend(
            offset=(10, 10),
            labelTextColor=theme.TEXT_PRI,
            labelTextSize="10pt",
        )
        _legend_ep.setParentItem(self._chart_ep.getPlotItem())
        self._line_ep  = self._chart_ep.plot(
            pen=pg.mkPen(theme.ACCENT, width=1.5),
            symbol="o", symbolSize=6,
            symbolBrush=theme.ACCENT, symbolPen=pg.mkPen(theme.BG_DEEP, width=1),
            name="Episode Reward")
        el.addWidget(self._chart_ep)
        self._tabs.addTab(ew, "🎯  Episodes")

        # Tab 3: Policy Losses — legend BEFORE plot() items
        lw = QWidget()
        ll = QVBoxLayout(lw)
        ll.setContentsMargins(4, 4, 4, 4)
        self._chart_loss = self._make_plot("PPO Losses vs Steps", "Steps", "Loss")
        _legend_loss = self._chart_loss.addLegend(
            offset=(10, 10),
            labelTextColor=theme.TEXT_PRI,
            labelTextSize="10pt",
        )
        _legend_loss.setParentItem(self._chart_loss.getPlotItem())
        self._line_ploss = self._chart_loss.plot(
            pen=pg.mkPen(theme.DANGER, width=2), name="Policy Loss")
        self._line_vloss = self._chart_loss.plot(
            pen=pg.mkPen(theme.WARN, width=2), name="Value Loss")
        self._line_ent   = self._chart_loss.plot(
            pen=pg.mkPen(theme.ACCENT2, width=1.5, style=Qt.PenStyle.DashLine), name="Entropy")
        ll.addWidget(self._chart_loss)
        self._tabs.addTab(lw, "📉  Losses")

        # Tab 4: Throughput
        fw = QWidget()
        fl = QVBoxLayout(fw)
        fl.setContentsMargins(4, 4, 4, 4)
        self._chart_fps = self._make_plot("Training Throughput", "Steps", "Steps / sec")
        _legend_fps = self._chart_fps.addLegend(
            offset=(10, 10),
            labelTextColor=theme.TEXT_PRI,
            labelTextSize="10pt",
        )
        _legend_fps.setParentItem(self._chart_fps.getPlotItem())
        self._line_fps  = self._chart_fps.plot(
            pen=pg.mkPen(theme.PLOT_COLORS[4], width=2.5), name="Throughput (FPS)")
        fl.addWidget(self._chart_fps)
        self._tabs.addTab(fw, "⚡  Throughput")

        # ── Controls ───────────────────────────────────────────────────────
        ctrl = QHBoxLayout()
        ctrl.addStretch()

        self._btn_start  = QPushButton("▶  Start Training")
        self._btn_start.setObjectName("btn_success")
        self._btn_start.clicked.connect(self.start_training)

        self._btn_pause  = QPushButton("⏸  Pause")
        self._btn_pause.setObjectName("btn_warn")
        self._btn_pause.setEnabled(False)
        self._btn_pause.setCheckable(True)
        self._btn_pause.toggled.connect(self._toggle_pause)

        self._btn_stop   = QPushButton("■  Stop")
        self._btn_stop.setObjectName("btn_danger")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self.stop_training)

        ctrl.addWidget(self._btn_stop)
        ctrl.addWidget(self._btn_pause)
        ctrl.addWidget(self._btn_start)
        root.addLayout(ctrl)

        # ── GUI poll timer ─────────────────────────────────────────────────
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_metrics)

    # ── Public API ─────────────────────────────────────────────────────────

    def apply_config(self, config: TrainingConfig) -> None:
        """Called by the main window to transfer config from other panels."""
        self._config = config
        self._lbl_title.setText(f"Live Training  —  {config.experiment_name}")
        self._progress.setMaximum(config.timesteps)
        self._lbl_status.setText(
            f"Ready: {config.algorithm.upper()}  •  "
            f"{config.timesteps:,} steps  •  ep_len={config.episode_steps}"
        )

    def start_training(self) -> None:
        if self._thread and self._thread.isRunning():
            return

        self._reset_buffers()
        self._set_status("running", f"Training {self._config.algorithm.upper()} …")
        self._progress.setValue(0)
        self._progress.setMaximum(self._config.timesteps)

        # Build the metrics callback
        self._metrics_cb = LiveMetricsCallback(
            on_metric_step=self._on_step_metric,
            on_metric_episode=self._on_episode_metric,
            total_timesteps=self._config.timesteps,
            sample_interval=10,
        )

        self._thread = TrainingThread(self._config, self._metrics_cb)
        self._thread.finished_signal.connect(self._on_finished)
        self._thread.start()

        self._btn_start.setEnabled(False)
        self._btn_pause.setEnabled(True)
        self._btn_stop.setEnabled(True)
        self._timer.start(400)

    def stop_training(self) -> None:
        if self._metrics_cb:
            self._metrics_cb.stop()
        self._set_status("stopped", "Stop requested — waiting for thread…")

    # ── Callbacks (called from training thread → NOT the GUI thread) ───────

    def _on_step_metric(self, m: TrainingStepMetric) -> None:
        """Accumulate metrics in thread-safe buffers (QMutex)."""
        self._mutex.lock()
        self._steps.append(float(m.timestep))
        self._rewards.append(m.reward)
        self._mean10.append(m.mean_reward_10)
        self._best.append(m.best_reward)
        self._policy_loss.append(m.policy_loss)
        self._value_loss.append(m.value_loss)
        self._entropy.append(m.entropy)
        self._fps_buf.append(m.fps)
        self._mutex.unlock()

    def _on_episode_metric(self, m: TrainingEpisodeMetric) -> None:
        self._mutex.lock()
        self._ep_nums.append(float(m.episode))
        self._ep_rewards.append(m.total_reward)
        self._mutex.unlock()

    # ── GUI timer poll ─────────────────────────────────────────────────────

    def _poll_metrics(self) -> None:
        self._mutex.lock()
        steps      = list(self._steps)
        rewards    = list(self._rewards)
        mean10     = list(self._mean10)
        best       = list(self._best)
        ploss      = list(self._policy_loss)
        vloss      = list(self._value_loss)
        entropy    = list(self._entropy)
        fps_buf    = list(self._fps_buf)
        ep_nums    = list(self._ep_nums)
        ep_rewards = list(self._ep_rewards)
        self._mutex.unlock()

        if not steps:
            return

        self._line_reward.setData(steps, rewards)
        self._line_mean10.setData(steps, mean10)
        self._line_best.setData(steps, best)
        self._line_ploss.setData(steps, ploss)
        self._line_vloss.setData(steps, vloss)
        self._line_ent.setData(steps, entropy)
        self._line_fps.setData(steps, fps_buf)

        if ep_nums:
            self._line_ep.setData(ep_nums, ep_rewards)

        # KPI updates
        last_step  = int(steps[-1]) if steps else 0
        last_rew   = rewards[-1]  if rewards else 0.0
        last_mean  = mean10[-1]   if mean10  else 0.0
        last_best  = best[-1]     if best    else 0.0
        last_fps   = fps_buf[-1]  if fps_buf else 0.0
        n_ep       = len(ep_nums)

        self._kpi_steps.findChildren(QLabel)[1].setText(f"{last_step:,}")
        self._kpi_episode.findChildren(QLabel)[1].setText(str(n_ep))
        self._kpi_reward.findChildren(QLabel)[1].setText(f"{last_rew:.3f}")
        self._kpi_mean10.findChildren(QLabel)[1].setText(f"{last_mean:.3f}")
        self._kpi_best.findChildren(QLabel)[1].setText(f"{last_best:.3f}")
        self._kpi_fps.findChildren(QLabel)[1].setText(f"{last_fps:.0f}")

        pct = int(100 * last_step / max(1, self._config.timesteps))
        self._progress.setValue(last_step)

        # ETA
        if last_fps > 0 and last_step < self._config.timesteps:
            remaining = (self._config.timesteps - last_step) / last_fps
            eta = _format_eta(remaining)
        else:
            eta = "—"
        self._kpi_eta.findChildren(QLabel)[1].setText(eta)

    def _on_finished(self, msg: str) -> None:
        self._timer.stop()
        self._poll_metrics()  # final update

        ok = "Error" not in msg
        self._set_status("done" if ok else "error", msg)

        self._btn_start.setEnabled(True)
        self._btn_pause.setEnabled(False)
        self._btn_stop.setEnabled(False)
        self._btn_pause.setChecked(False)

    def _toggle_pause(self, checked: bool) -> None:
        if not self._metrics_cb:
            return
        if checked:
            self._metrics_cb.pause()
            self._set_status("paused", "Training paused.")
            self._btn_pause.setText("▶  Resume")
        else:
            self._metrics_cb.resume()
            self._set_status("running", "Training resumed.")
            self._btn_pause.setText("⏸  Pause")

    # ── Private helpers ────────────────────────────────────────────────────

    def _set_status(self, kind: str, msg: str) -> None:
        colors = {
            "running": theme.ACCENT2,
            "paused":  theme.WARN,
            "stopped": theme.TEXT_SEC,
            "done":    theme.ACCENT2,
            "error":   theme.DANGER,
        }
        badges = {
            "running": "● TRAINING",
            "paused":  "⏸ PAUSED",
            "stopped": "■ STOPPED",
            "done":    "✓ DONE",
            "error":   "✗ ERROR",
        }
        color = colors.get(kind, theme.TEXT_SEC)
        badge = badges.get(kind, kind.upper())
        self._badge.setText(badge)
        self._badge.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: 700;"
            f" background: {color}22; border: 1px solid {color};"
            " border-radius: 10px; padding: 3px 12px;"
        )
        self._lbl_status.setText(msg)
        self._lbl_status.setStyleSheet(f"color: {color}; font-size: 13px; border: none;")

    def _reset_buffers(self) -> None:
        self._mutex.lock()
        for lst in (self._steps, self._rewards, self._mean10, self._best,
                    self._policy_loss, self._value_loss, self._entropy,
                    self._fps_buf, self._ep_rewards, self._ep_nums):
            lst.clear()
        self._mutex.unlock()

    @staticmethod
    def _make_plot(title: str, x_label: str, y_label: str) -> pg.PlotWidget:
        pw = pg.PlotWidget()
        pw.setBackground(theme.BG_CARD)
        # Brighter title so it's clearly readable
        pw.setTitle(title, color=theme.TEXT_PRI, size="12pt")
        pw.setLabel("left",   y_label, color=theme.TEXT_PRI,
                    **{"font-size": "11pt"})
        pw.setLabel("bottom", x_label, color=theme.TEXT_PRI,
                    **{"font-size": "11pt"})
        pw.showGrid(x=True, y=True, alpha=0.12)
        left_ax   = pw.getAxis("left")
        bottom_ax = pw.getAxis("bottom")
        left_ax.setTextPen(pg.mkPen(color=theme.TEXT_PRI))
        bottom_ax.setTextPen(pg.mkPen(color=theme.TEXT_PRI))
        left_ax.setPen(pg.mkPen(color=theme.BORDER, width=1))
        bottom_ax.setPen(pg.mkPen(color=theme.BORDER, width=1))
        return pw

    @staticmethod
    def _kpi(label: str, value: str, color: str) -> QFrame:
        f = QFrame()
        f.setStyleSheet(f"""
            QFrame {{
                background: {theme.BG_CARD};
                border: 1px solid {theme.BORDER};
                border-radius: 10px;
            }}
        """)
        lay = QVBoxLayout(f)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(2)
        lbl_l = QLabel(label.upper())
        lbl_l.setStyleSheet(
            f"color: {theme.TEXT_SEC}; font-size: 10px; font-weight: 700;"
            " letter-spacing: 1px; border: none; background: transparent;"
        )
        lbl_v = QLabel(value)
        lbl_v.setStyleSheet(
            f"color: {color}; font-size: 18px; font-weight: 800;"
            " border: none; background: transparent;"
        )
        lay.addWidget(lbl_l)
        lay.addWidget(lbl_v)
        return f


def _format_eta(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    else:
        return f"{seconds / 3600:.1f}h"
