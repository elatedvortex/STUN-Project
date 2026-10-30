import sys
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtWidgets import QApplication
from config.loader import build_registry_from_config
from dashboard.app import MainWindow
import time

app = QApplication(sys.argv)
registry = build_registry_from_config("config/scheduler.yaml")
window = MainWindow(registry=registry)
window.resize(1280, 720)
window.show()

for _ in range(50):
    app.processEvents()
    time.sleep(0.01)

pixmap = window.grab()
pixmap.save("dashboard_screenshot.png")
print("Screenshot saved to dashboard_screenshot.png")
