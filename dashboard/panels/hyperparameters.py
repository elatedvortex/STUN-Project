from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QSpinBox, QDoubleSpinBox, QPushButton, QFormLayout, QGroupBox, QScrollArea, QTabWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from dashboard import theme

class HyperparametersPanel(QWidget):
    """Panel for configuring RL algorithm hyperparameters."""
    
    def __init__(self):
        super().__init__()
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # Title
        title = QLabel("Hyperparameters Configuration")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {theme.TEXT_PRI};")
        main_layout.addWidget(title)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {theme.BORDER}; border-radius: 4px; }}
            QTabBar::tab {{ background: {theme.BG_DEEP}; color: {theme.TEXT_SEC}; padding: 10px 20px; }}
            QTabBar::tab:selected {{ background: {theme.BG_CARD}; color: {theme.ACCENT}; font-weight: bold; border-bottom: 2px solid {theme.ACCENT}; }}
        """)
        
        # PPO Tab
        self.ppo_tab = QWidget()
        ppo_layout = QFormLayout(self.ppo_tab)
        ppo_layout.setContentsMargins(20, 20, 20, 20)
        ppo_layout.setSpacing(15)
        
        self.ppo_lr = QDoubleSpinBox(); self.ppo_lr.setDecimals(5); self.ppo_lr.setSingleStep(0.0001); self.ppo_lr.setValue(0.0003)
        self.ppo_nsteps = QSpinBox(); self.ppo_nsteps.setRange(16, 4096); self.ppo_nsteps.setValue(256)
        self.ppo_batch = QSpinBox(); self.ppo_batch.setRange(8, 2048); self.ppo_batch.setValue(64)
        self.ppo_epochs = QSpinBox(); self.ppo_epochs.setRange(1, 100); self.ppo_epochs.setValue(4)
        self.ppo_gamma = QDoubleSpinBox(); self.ppo_gamma.setDecimals(3); self.ppo_gamma.setSingleStep(0.01); self.ppo_gamma.setValue(0.99)
        self.ppo_ent_coef = QDoubleSpinBox(); self.ppo_ent_coef.setDecimals(4); self.ppo_ent_coef.setSingleStep(0.001); self.ppo_ent_coef.setValue(0.0)
        
        for w in [self.ppo_lr, self.ppo_nsteps, self.ppo_batch, self.ppo_epochs, self.ppo_gamma, self.ppo_ent_coef]:
            w.setStyleSheet(self._input_style())
            
        ppo_layout.addRow("Learning Rate:", self.ppo_lr)
        ppo_layout.addRow("n_steps (Rollout Length):", self.ppo_nsteps)
        ppo_layout.addRow("Batch Size:", self.ppo_batch)
        ppo_layout.addRow("n_epochs:", self.ppo_epochs)
        ppo_layout.addRow("Gamma (Discount Factor):", self.ppo_gamma)
        ppo_layout.addRow("Entropy Coefficient:", self.ppo_ent_coef)
        
        self.tabs.addTab(self.ppo_tab, "PPO Configuration")
        
        # SAC Tab
        self.sac_tab = QWidget()
        sac_layout = QFormLayout(self.sac_tab)
        sac_layout.setContentsMargins(20, 20, 20, 20)
        sac_layout.setSpacing(15)
        
        self.sac_lr = QDoubleSpinBox(); self.sac_lr.setDecimals(5); self.sac_lr.setValue(0.0003)
        self.sac_buffer = QSpinBox(); self.sac_buffer.setRange(1000, 1000000); self.sac_buffer.setValue(100000)
        self.sac_batch = QSpinBox(); self.sac_batch.setRange(8, 2048); self.sac_batch.setValue(256)
        self.sac_tau = QDoubleSpinBox(); self.sac_tau.setDecimals(3); self.sac_tau.setValue(0.005)
        self.sac_gamma = QDoubleSpinBox(); self.sac_gamma.setDecimals(3); self.sac_gamma.setValue(0.99)
        self.sac_ent = QComboBox(); self.sac_ent.addItems(["auto", "custom"])
        
        for w in [self.sac_lr, self.sac_buffer, self.sac_batch, self.sac_tau, self.sac_gamma, self.sac_ent]:
            w.setStyleSheet(self._input_style())
            
        sac_layout.addRow("Learning Rate:", self.sac_lr)
        sac_layout.addRow("Buffer Size:", self.sac_buffer)
        sac_layout.addRow("Batch Size:", self.sac_batch)
        sac_layout.addRow("Tau (Polyak Update):", self.sac_tau)
        sac_layout.addRow("Gamma:", self.sac_gamma)
        sac_layout.addRow("Target Entropy:", self.sac_ent)
        
        self.tabs.addTab(self.sac_tab, "SAC Configuration")
        
        main_layout.addWidget(self.tabs)
        
        # Actions
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_reset = QPushButton("↺ Reset Defaults")
        self.btn_reset.setStyleSheet(self._btn_style(theme.TEXT_SEC))
        
        self.btn_next = QPushButton("▶ Proceed to Reward Config")
        self.btn_next.setStyleSheet(self._btn_style(theme.ACCENT))
        
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addWidget(self.btn_next)
        main_layout.addLayout(btn_layout)

    def _input_style(self) -> str:
        return f"""
            QWidget {{
                background-color: {theme.BG_DEEP}; border: 1px solid {theme.BORDER};
                border-radius: 4px; padding: 5px; color: {theme.TEXT_PRI};
            }}
        """

    def _btn_style(self, color: str) -> str:
        return f"""
            QPushButton {{
                background-color: {color}; color: white; border: none;
                border-radius: 4px; padding: 8px 16px; font-weight: bold; font-size: 14px;
            }}
            QPushButton:hover {{ opacity: 0.8; }}
        """
