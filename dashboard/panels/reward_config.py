from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, 
    QDoubleSpinBox, QPushButton, QFormLayout, QGroupBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from dashboard import theme

class RewardConfigPanel(QWidget):
    """Panel for configuring RL Reward Shaping logic."""
    
    def __init__(self):
        super().__init__()
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        title = QLabel("Reward Function Configuration")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {theme.TEXT_PRI};")
        main_layout.addWidget(title)
        
        desc = QLabel("Configure the multi-objective reward shaping weights. The final scalar reward given to the agent is a weighted sum of the enabled components.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {theme.TEXT_SEC}; font-size: 13px; margin-bottom: 10px;")
        main_layout.addWidget(desc)
        
        # Throughput Group
        grp_throughput = QGroupBox("Benchmark Throughput")
        grp_throughput.setStyleSheet(self._groupbox_style())
        lyt_throughput = QFormLayout(grp_throughput)
        
        self.chk_throughput = QCheckBox("Enable Throughput Reward")
        self.chk_throughput.setChecked(True)
        self.spin_throughput_w = QDoubleSpinBox(); self.spin_throughput_w.setRange(-10, 10); self.spin_throughput_w.setValue(1.0)
        self.spin_throughput_w.setStyleSheet(self._input_style())
        
        lyt_throughput.addRow(self.chk_throughput)
        lyt_throughput.addRow("Weight:", self.spin_throughput_w)
        main_layout.addWidget(grp_throughput)
        
        # System Health Group
        grp_health = QGroupBox("System Health Penalties")
        grp_health.setStyleSheet(self._groupbox_style())
        lyt_health = QFormLayout(grp_health)
        
        self.chk_latency = QCheckBox("Enable Latency Penalty")
        self.chk_latency.setChecked(True)
        self.spin_latency_w = QDoubleSpinBox(); self.spin_latency_w.setRange(-10, 10); self.spin_latency_w.setValue(-0.5)
        self.spin_latency_w.setStyleSheet(self._input_style())
        
        self.chk_switches = QCheckBox("Enable Context Switch Penalty")
        self.chk_switches.setChecked(True)
        self.spin_switches_w = QDoubleSpinBox(); self.spin_switches_w.setRange(-10, 10); self.spin_switches_w.setValue(-0.1)
        self.spin_switches_w.setStyleSheet(self._input_style())
        
        lyt_health.addRow(self.chk_latency)
        lyt_health.addRow("Latency Weight:", self.spin_latency_w)
        lyt_health.addRow(self.chk_switches)
        lyt_health.addRow("Context Switch Weight:", self.spin_switches_w)
        main_layout.addWidget(grp_health)
        
        # Stability Group
        grp_stability = QGroupBox("Action Stability")
        grp_stability.setStyleSheet(self._groupbox_style())
        lyt_stability = QFormLayout(grp_stability)
        
        self.chk_stability = QCheckBox("Enable Stability Bonus (Reward for fewer changes)")
        self.chk_stability.setChecked(True)
        self.spin_stability_w = QDoubleSpinBox(); self.spin_stability_w.setRange(-10, 10); self.spin_stability_w.setValue(0.2)
        self.spin_stability_w.setStyleSheet(self._input_style())
        
        lyt_stability.addRow(self.chk_stability)
        lyt_stability.addRow("Stability Bonus Weight:", self.spin_stability_w)
        main_layout.addWidget(grp_stability)
        
        main_layout.addStretch()
        
        # Actions
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_save = QPushButton("💾 Save Reward Profile")
        self.btn_save.setStyleSheet(self._btn_style(theme.ACCENT))
        btn_layout.addWidget(self.btn_save)
        main_layout.addLayout(btn_layout)

    def _groupbox_style(self) -> str:
        return f"""
            QGroupBox {{
                background-color: {theme.BG_CARD}; border: 1px solid {theme.BORDER};
                border-radius: 6px; margin-top: 1ex; font-weight: bold; color: {theme.TEXT_PRI}; padding: 15px;
            }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; color: {theme.ACCENT}; }}
        """

    def _input_style(self) -> str:
        return f"QWidget {{ background-color: {theme.BG_DEEP}; border: 1px solid {theme.BORDER}; border-radius: 4px; padding: 5px; color: {theme.TEXT_PRI}; }}"

    def _btn_style(self, color: str) -> str:
        return f"QPushButton {{ background-color: {color}; color: white; border: none; border-radius: 4px; padding: 8px 16px; font-weight: bold; font-size: 14px; }} QPushButton:hover {{ opacity: 0.8; }}"
