from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class PlaceholderPanel(QWidget):
    def __init__(self, title: str):
        super().__init__()
        layout = QVBoxLayout(self)
        
        lbl = QLabel(title)
        lbl.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #64748B;")
        
        desc = QLabel("This module is currently under development.")
        desc.setFont(QFont("Segoe UI", 12))
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #475569;")
        
        layout.addStretch()
        layout.addWidget(lbl)
        layout.addWidget(desc)
        layout.addStretch()
