"""
Statistics panel — Gutenberg-Richter, per-station residuals, network report.
"""
from __future__ import annotations

from typing import List

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTextEdit, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView, QFileDialog, QMessageBox,
)

from core.stats import (
    compute_network_report, compute_station_residuals,
    format_network_report,
)


class StatsPanel(QWidget):
    """
    Two-tab panel:
      Network Report  — text summary + G-R b-value
      Station Residuals — sortable table
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: list[dict] = []
        self._build_ui()

    # ------------------------------------------------------------------ #

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        # Export buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self._exp_report_btn = QPushButton("Export Report (.txt)")
        self._exp_report_btn.clicked.connect(self._export_report)
        btn_row.addWidget(self._exp_report_btn)

        self._exp_residuals_btn = QPushButton("Export Residuals (.csv)")
        self._exp_residuals_btn.clicked.connect(self._export_residuals)
        btn_row.addWidget(self._exp_residuals_btn)

        btn_row.addStretch()
        outer.addLayout(btn_row)

        self._tabs = QTabWidget()
        outer.addWidget(self._tabs, 1)

        # Tab 1: network report
        self._report_edit = QTextEdit()
        self._report_edit.setReadOnly(True)
        self._report_edit.setFontFamily("Courier New, Courier, monospace")
        self._tabs.addTab(self._report_edit, "Network Report")

        # Tab 2: per-station residuals
        self._resid_table = QTableWidget()
        self._resid_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._resid_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._resid_table.setAlternatingRowColors(True)
        self._resid_table.setSortingEnabled(True)
        self._resid_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._tabs.addTab(self._resid_table, "Station Residuals")

    # ------------------------------------------------------------------ #

    def populate(self, results: list[dict]):
        self._results = results

        # Network report
        report = compute_network_report(results)
        self._report_edit.setPlainText(format_network_report(report))

        # Station residuals
        rows = compute_station_residuals(results)
        cols = [
            ("Network",  "station_network"),
            ("Station",  "station_code"),
            ("Phase",    "phase"),
            ("N",        "n_arrivals"),
            ("N used",   "n_used"),
            ("Mean res (s)", "mean_residual"),
            ("Std (s)",  "std_residual"),
            ("Min (s)",  "min_residual"),
            ("Max (s)",  "max_residual"),
            ("Mean dist (°)", "mean_distance"),
        ]

        self._resid_table.setColumnCount(len(cols))
        self._resid_table.setHorizontalHeaderLabels([c[0] for c in cols])
        self._resid_table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            for c, (_, key) in enumerate(cols):
                val = row.get(key)
                item = QTableWidgetItem(
                    "" if val is None else str(val)
                )
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if isinstance(val, (int, float)):
                    item.setData(Qt.UserRole, val)
                self._resid_table.setItem(r, c, item)

    # ------------------------------------------------------------------ #

    def _export_report(self):
        if not self._results:
            QMessageBox.information(self, "No data", "Run processing first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Report", "catalog_report.txt",
            "Text files (*.txt);;All files (*)"
        )
        if path:
            report = compute_network_report(self._results)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(format_network_report(report))

    def _export_residuals(self):
        if not self._results:
            QMessageBox.information(self, "No data", "Run processing first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Residuals", "station_residuals.csv",
            "CSV files (*.csv);;All files (*)"
        )
        if not path:
            return
        import csv
        rows = compute_station_residuals(self._results)
        if not rows:
            return
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
