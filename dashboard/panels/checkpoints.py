"""
dashboard/panels/checkpoints.py — Checkpoint Management panel.

Scans data/checkpoints/ for real .zip SB3 model files.
Supports: Refresh, Evaluate Selected (wires to EvaluationPanel),
Resume Training (wires to LiveTrainingPanel), Delete.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from dashboard import theme


class CheckpointsPanel(QWidget):
    """Panel for managing saved RL model checkpoints (real filesystem)."""

    # Emitted when user requests evaluation of a checkpoint
    evaluate_requested = pyqtSignal(str, str)   # (path, algorithm)
    # Emitted when user requests resuming from a checkpoint
    resume_requested   = pyqtSignal(str, str)   # (path, algorithm)

    def __init__(self, checkpoint_dir: str = "data/checkpoints", parent=None) -> None:
        super().__init__(parent)
        self._ckpt_dir = Path(checkpoint_dir)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Checkpoint Management")
        title.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {theme.TEXT_PRI}; border: none;")
        hdr.addWidget(title)
        hdr.addStretch()
        self._lbl_dir = QLabel(f"📁  {self._ckpt_dir.resolve()}")
        self._lbl_dir.setStyleSheet(f"color: {theme.TEXT_SEC}; font-size: 12px; border: none;")
        hdr.addWidget(self._lbl_dir)
        main_layout.addLayout(hdr)

        desc = QLabel(
            "View, evaluate, resume, or delete saved Stable-Baselines3 model checkpoints. "
            "Select a row and use the action buttons below."
        )
        desc.setStyleSheet(f"color: {theme.TEXT_SEC}; font-size: 13px; border: none;")
        desc.setWordWrap(True)
        main_layout.addWidget(desc)

        # Summary strip
        self._lbl_summary = QLabel("")
        self._lbl_summary.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12px; border: none;")
        main_layout.addWidget(self._lbl_summary)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["File Name", "Algorithm", "Steps", "Size", "Date Modified", "Status"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self._on_selection)
        main_layout.addWidget(self.table, 1)

        # Actions
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_refresh = QPushButton("↻  Refresh")
        self.btn_refresh.clicked.connect(self._load_checkpoints)

        self.btn_open_dir = QPushButton("📂  Open Folder")
        self.btn_open_dir.clicked.connect(self._open_dir)

        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_open_dir)
        btn_layout.addStretch()

        self.btn_eval = QPushButton("📊  Evaluate Selected")
        self.btn_eval.setObjectName("btn_warn")
        self.btn_eval.setEnabled(False)
        self.btn_eval.clicked.connect(self._evaluate_selected)

        self.btn_resume = QPushButton("▶  Resume Training")
        self.btn_resume.setObjectName("btn_success")
        self.btn_resume.setEnabled(False)
        self.btn_resume.clicked.connect(self._resume_selected)

        self.btn_delete = QPushButton("🗑  Delete Selected")
        self.btn_delete.setObjectName("btn_danger")
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._delete_selected)

        btn_layout.addWidget(self.btn_eval)
        btn_layout.addWidget(self.btn_resume)
        btn_layout.addWidget(self.btn_delete)
        main_layout.addLayout(btn_layout)

        self._lbl_action = QLabel("")
        self._lbl_action.setStyleSheet(f"color: {theme.ACCENT2}; font-size: 12px; border: none;")
        main_layout.addWidget(self._lbl_action)

        self._load_checkpoints()

    # ── Public ──────────────────────────────────────────────────────────

    def set_checkpoint_dir(self, path: str) -> None:
        self._ckpt_dir = Path(path)
        self._lbl_dir.setText(f"📁  {self._ckpt_dir.resolve()}")
        self._load_checkpoints()

    # ── Private ──────────────────────────────────────────────────────────

    def _load_checkpoints(self) -> None:
        self.table.setRowCount(0)

        if not self._ckpt_dir.is_dir():
            self._lbl_summary.setText(
                f"Directory not found: {self._ckpt_dir}  —  checkpoints will appear after first training run."
            )
            return

        files = sorted(
            self._ckpt_dir.glob("*.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for i, f in enumerate(files):
            self.table.insertRow(i)

            algo = "SAC" if "sac" in f.name.lower() else "PPO"

            # Extract step count from filename (e.g. ppo_20000_steps.zip)
            steps_str = "—"
            for part in f.stem.split("_"):
                if part.isdigit():
                    steps_str = f"{int(part):,}"
                    break

            size_mb = f.stat().st_size / 1_048_576
            mtime   = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            status  = "✓  Valid"

            # Quick validation: file must be > 1 KB
            if f.stat().st_size < 1024:
                status = "⚠  Suspicious"

            row_data = [f.name, algo, steps_str, f"{size_mb:.2f} MB", mtime, status]
            for j, val in enumerate(row_data):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if j == 1:   # algo
                    item.setForeground(QColor(theme.ACCENT))
                elif j == 5:  # status
                    color = theme.ACCENT2 if "Valid" in val else theme.WARN
                    item.setForeground(QColor(color))
                self.table.setItem(i, j, item)

        n = self.table.rowCount()
        total_mb = sum(
            f.stat().st_size / 1_048_576 for f in self._ckpt_dir.glob("*.zip")
        ) if self._ckpt_dir.is_dir() else 0

        self._lbl_summary.setText(
            f"{n} checkpoint(s) found  •  Total: {total_mb:.1f} MB"
            f"  •  Directory: {self._ckpt_dir.resolve()}"
        )
        self._update_action_buttons()

    def _on_selection(self) -> None:
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        has_selection = bool(self.table.selectedItems())
        self.btn_eval.setEnabled(has_selection)
        self.btn_resume.setEnabled(has_selection)
        self.btn_delete.setEnabled(has_selection)

    def _selected_path_algo(self) -> tuple[Path | None, str]:
        rows = self.table.selectedItems()
        if not rows:
            return None, "ppo"
        row = self.table.currentRow()
        name = self.table.item(row, 0).text()
        algo = self.table.item(row, 1).text().lower()
        return self._ckpt_dir / name, algo

    def _evaluate_selected(self) -> None:
        path, algo = self._selected_path_algo()
        if path and path.is_file():
            self._lbl_action.setText(f"Requesting evaluation of {path.name}…")
            self.evaluate_requested.emit(str(path), algo)

    def _resume_selected(self) -> None:
        path, algo = self._selected_path_algo()
        if path and path.is_file():
            self._lbl_action.setText(f"Requesting resume from {path.name}…")
            self.resume_requested.emit(str(path), algo)

    def _delete_selected(self) -> None:
        path, _ = self._selected_path_algo()
        if not path:
            return
        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Permanently delete {path.name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                path.unlink()
                self._lbl_action.setText(f"Deleted {path.name}.")
                self._load_checkpoints()
            except Exception as exc:
                self._lbl_action.setText(f"Error: {exc}")
                self._lbl_action.setStyleSheet(f"color: {theme.DANGER}; font-size: 12px; border: none;")

    def _open_dir(self) -> None:
        import subprocess
        path = str(self._ckpt_dir.resolve())
        try:
            subprocess.Popen(["xdg-open", path])
        except Exception:
            pass
