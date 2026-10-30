"""Opt-in offscreen dashboard lifecycle check in an isolated directory."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(os.environ.get("RUN_GUI_CHECKS") != "1",
                    reason="set RUN_GUI_CHECKS=1 for offscreen Qt integration")
def test_dashboard_opens_receives_snapshot_and_closes(tmp_path):
    if importlib.util.find_spec("PyQt6") is None or importlib.util.find_spec("pyqtgraph") is None:
        pytest.skip("dashboard dependencies not installed")
    root = Path(__file__).resolve().parents[1]
    code = """
import sys
sys.path.insert(0, sys.argv[1])
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from config.loader import build_registry_from_config
from scheduler.backend import SysctlBackend
def forbidden(*args):
    raise AssertionError('dashboard smoke must never write sysctls')
SysctlBackend.write = forbidden
from dashboard.app import MainWindow
errors = []
sys.excepthook = lambda kind, value, tb: errors.append(str(value))
app = QApplication([])
registry = build_registry_from_config(sys.argv[1] + '/config/scheduler.yaml')
window = MainWindow(registry, controller=None, interval_ms=100)
seen = []
window._worker.snapshot_ready.connect(lambda snapshot: seen.append(snapshot))
window.show()
def finish():
    window.close()
    app.quit()
QTimer.singleShot(750, finish)
app.exec()
assert seen, 'no monitor snapshots received'
assert not window._worker.isRunning(), 'monitor thread survived window close'
assert not errors, errors
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code, str(root)], cwd=tmp_path,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-5000:]
