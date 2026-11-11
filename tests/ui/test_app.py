import os
import subprocess
import sys


def test_job_model_uses_ascii_progress_and_native_theme():
    script = r"""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from mt_engine.ui.app import JobTableModel
from mt_engine.application import BatchJobSnapshot, BatchJobState

app = QApplication([])
model = JobTableModel()
model.replace((BatchJobSnapshot(
    "J0001", Path("C:/songs/example"), BatchJobState.RUNNING, 42, "Rendering"
),))
assert model.data(model.index(0, 3), Qt.DisplayRole) == "42%"
assert model.data(model.index(0, 3), Qt.UserRole) == 42
assert model.data(model.index(0, 0), Qt.DisplayRole) == "J0001"
assert app.styleSheet() == ""
"""
    environment = os.environ.copy()
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == 0, result.stderr
