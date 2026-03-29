"""
Main application window — PyQt5 GUI for the SeisComP Station Data Extractor.

Layout
──────
  ┌─ toolbar ──────────────────────────────────────────────────────────┐
  │  [Theme] [Presets ▾]  [Save preset]                                │
  └────────────────────────────────────────────────────────────────────┘
  ┌─ left panel ───────────────┐  ┌─ right panel ──────────────────────┐
  │  Drop Zone                 │  │  Field Selector                    │
  │  File List                 │  │  (collapsible categories +         │
  │  ─────────────────────     │  │   search + global buttons)         │
  │  Filter Panel (tabbed)     │  │                                    │
  │  ─────────────────────     │  │                                    │
  │  Output format  (combo)    │  │                                    │
  │  ─────────────────────     │  │                                    │
  │  [🚀 Process Files]        │  │                                    │
  └────────────────────────────┘  └────────────────────────────────────┘
  ┌─ progress area ─────────────────────────────────────────────────────┐
  ┌─ results / statistics tabs ─────────────────────────────────────────┐
  │  Summary + ZIP buttons + event cards  |  Stats panel                │
  └─────────────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QSize
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QProgressBar, QListWidget,
    QListWidgetItem, QFileDialog, QTabWidget, QToolBar,
    QSizePolicy, QGroupBox, QMessageBox,
)

from core.filters import FilterConfig
from core.parser import SeisCompParser
from .drop_zone import DropZone
from .field_selector import FieldSelector
from .filter_panel import FilterPanel
from .results_panel import ResultsPanel
from .stats_panel import StatsPanel
from .preset_dialog import PresetDialog
from core.presets import load_preset, save_preset, list_presets
from . import styles


# ──────────────────────────────────────────────────────────────────────────────
# Background worker
# ──────────────────────────────────────────────────────────────────────────────

class _WorkerSignals(QObject):
    progress       = pyqtSignal(int, int, str)
    event_progress = pyqtSignal(int, int, str)
    finished       = pyqtSignal(list)
    error          = pyqtSignal(str)


class _ProcessWorker(QThread):
    def __init__(self, files: List[str], filters: FilterConfig):
        super().__init__()
        self.files   = files
        self.filters = filters
        self.signals = _WorkerSignals()
        self._parser = SeisCompParser()

    def run(self):
        all_results = []
        try:
            for i, path in enumerate(self.files):
                self.signals.progress.emit(
                    i, len(self.files),
                    f"Parsing {Path(path).name}  ({i+1}/{len(self.files)})"
                )
                results = self._parser.parse_file(
                    path, self.filters,
                    progress_callback=lambda cur, tot, msg:
                        self.signals.event_progress.emit(cur, tot, msg),
                )
                all_results.extend(results)
        except Exception as exc:
            self.signals.error.emit(str(exc))
            return
        self.signals.finished.emit(all_results)


# ──────────────────────────────────────────────────────────────────────────────
# File list widget
# ──────────────────────────────────────────────────────────────────────────────

class _FileListWidget(QFrame):
    files_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._files: List[str] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        header = QHBoxLayout()
        self._count_lbl = QLabel("No files selected")
        self._count_lbl.setStyleSheet("font-weight:600;")
        header.addWidget(self._count_lbl, 1)

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("btn_secondary")
        clear_btn.setFixedSize(58, 24)
        clear_btn.clicked.connect(self._clear)
        header.addWidget(clear_btn)
        lay.addLayout(header)

        self._list = QListWidget()
        self._list.setFixedHeight(100)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        lay.addWidget(self._list)

    def add_files(self, paths: List[str]):
        existing = set(self._files)
        for p in paths:
            if p not in existing:
                self._files.append(p)
                existing.add(p)
        self._refresh()

    def _clear(self):
        self._files.clear()
        self._refresh()

    def _refresh(self):
        self._list.clear()
        for p in self._files:
            size_kb = Path(p).stat().st_size / 1024 if Path(p).exists() else 0
            self._list.addItem(
                QListWidgetItem(f"  {Path(p).name}  ({size_kb:.1f} KB)")
            )
        n = len(self._files)
        self._count_lbl.setText(
            "No files selected" if n == 0 else f"{n} file{'s' if n>1 else ''} queued"
        )
        self.files_changed.emit(self._files)

    @property
    def file_paths(self) -> List[str]:
        return list(self._files)


# ──────────────────────────────────────────────────────────────────────────────
# Main window
# ──────────────────────────────────────────────────────────────────────────────

# Format options: (label, value)
_FORMATS = [
    ("CSV",      "csv"),
    ("GeoJSON",  "geojson"),
    ("Both CSV+GeoJSON", "both"),
    ("HYPO71 phase file", "hypo71"),
    ("Nordic / SEISAN",   "nordic"),
    ("SQLite database",   "sqlite"),
    ("Parquet",           "parquet"),
]


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self._theme   = "light"
        self._results: List[dict] = []
        self._worker: _ProcessWorker | None = None

        self.setWindowTitle("SeisComP Station Data Extractor")
        self.setMinimumSize(1100, 720)
        self.resize(1280, 860)

        self._build_toolbar()
        self._build_central()
        self._build_status_bar()
        self._apply_theme()

    # ------------------------------------------------------------------ #
    # Construction                                                         #
    # ------------------------------------------------------------------ #

    def _build_toolbar(self):
        tb = QToolBar("Main toolbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        self.addToolBar(tb)

        title_lbl = QLabel("  🌍 SeisComP Extractor  ")
        title_lbl.setStyleSheet("font-size:14px; font-weight:700;")
        tb.addWidget(title_lbl)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

        tb.addWidget(QLabel("Preset: "))
        self._preset_combo = QComboBox()
        self._preset_combo.setMinimumWidth(160)
        self._preset_combo.setToolTip("Select a saved preset")
        self._refresh_preset_combo()
        tb.addWidget(self._preset_combo)

        load_btn = QPushButton("Load")
        load_btn.setFixedSize(54, 28)
        load_btn.clicked.connect(self._load_preset_from_combo)
        tb.addWidget(load_btn)

        manage_btn = QPushButton("Manage…")
        manage_btn.setFixedSize(74, 28)
        manage_btn.clicked.connect(self._open_preset_manager)
        tb.addWidget(manage_btn)

        tb.addSeparator()

        theme_btn = QPushButton("🌙 Dark")
        theme_btn.setFixedSize(76, 28)
        theme_btn.setToolTip("Toggle dark / light theme")
        theme_btn.clicked.connect(self._toggle_theme)
        self._theme_btn = theme_btn
        tb.addWidget(theme_btn)

        tb.addWidget(QLabel("  "))

    # ------------------------------------------------------------------ #

    def _build_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(12, 8, 12, 8)
        outer.setSpacing(10)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(6)

        # ── LEFT panel ───────────────────────────────────────────────
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(10)

        self._section_label(left_lay, "📁 Upload XML Files")
        self._drop_zone = DropZone()
        self._drop_zone.files_dropped.connect(self._on_files_dropped)
        left_lay.addWidget(self._drop_zone)

        self._file_list = _FileListWidget()
        self._file_list.files_changed.connect(self._update_process_btn)
        left_lay.addWidget(self._file_list)

        self._section_label(left_lay, "🔍 Filters")
        filter_card = QFrame()
        filter_card.setObjectName("card")
        fc_lay = QVBoxLayout(filter_card)
        fc_lay.setContentsMargins(12, 10, 12, 10)
        self._filter_panel = FilterPanel()
        fc_lay.addWidget(self._filter_panel)
        left_lay.addWidget(filter_card)

        self._section_label(left_lay, "📄 Output Format")
        fmt_card = QFrame()
        fmt_card.setObjectName("card")
        fmt_lay = QHBoxLayout(fmt_card)
        fmt_lay.setContentsMargins(12, 8, 12, 8)

        self._fmt_combo = QComboBox()
        for label, _ in _FORMATS:
            self._fmt_combo.addItem(label)
        self._fmt_combo.setToolTip("Choose output format")
        fmt_lay.addWidget(QLabel("Format:"))
        fmt_lay.addWidget(self._fmt_combo, 1)
        left_lay.addWidget(fmt_card)

        self._proc_btn = QPushButton("🚀  Process Files")
        self._proc_btn.setObjectName("btn_process")
        self._proc_btn.setEnabled(False)
        self._proc_btn.clicked.connect(self._start_processing)
        left_lay.addWidget(self._proc_btn)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("%p%  %v/%m")
        self._progress_bar.setVisible(False)
        left_lay.addWidget(self._progress_bar)

        self._prog_lbl = QLabel()
        self._prog_lbl.setStyleSheet("font-size: 12px; color: #7f8c8d;")
        self._prog_lbl.setVisible(False)
        left_lay.addWidget(self._prog_lbl)

        left_lay.addStretch()
        splitter.addWidget(left)
        splitter.setStretchFactor(0, 2)

        # ── RIGHT panel: field selector ───────────────────────────────
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(6)

        self._section_label(right_lay, "🎯 Select Output Fields")
        self._field_selector = FieldSelector()
        self._field_selector.selection_changed.connect(self._update_process_btn)
        right_lay.addWidget(self._field_selector, 1)

        splitter.addWidget(right)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([420, 660])

        outer.addWidget(splitter, 3)

        # ── Results / Statistics tabs ─────────────────────────────────
        self._result_tabs = QTabWidget()
        self._result_tabs.setVisible(False)

        self._results_panel = ResultsPanel()
        self._result_tabs.addTab(self._results_panel, "📊 Results")

        self._stats_panel = StatsPanel()
        self._result_tabs.addTab(self._stats_panel, "📈 Statistics")

        outer.addWidget(self._result_tabs, 2)

    def _section_label(self, layout, text: str):
        lbl = QLabel(text)
        lbl.setObjectName("section_title")
        layout.addWidget(lbl)

    # ------------------------------------------------------------------ #

    def _build_status_bar(self):
        self._status_bar = self.statusBar()
        self._status_lbl = QLabel("Ready")
        self._status_bar.addWidget(self._status_lbl, 1)
        self._schema_lbl = QLabel("")
        self._schema_lbl.setStyleSheet("color: #3498db; font-size: 12px;")
        self._status_bar.addPermanentWidget(self._schema_lbl)

    # ------------------------------------------------------------------ #
    # Theme                                                                #
    # ------------------------------------------------------------------ #

    def _apply_theme(self):
        sheet = styles.LIGHT if self._theme == "light" else styles.DARK
        QApplication.instance().setStyleSheet(sheet)

    def _toggle_theme(self):
        self._theme = "dark" if self._theme == "light" else "light"
        self._theme_btn.setText("☀ Light" if self._theme == "dark" else "🌙 Dark")
        self._apply_theme()

    # ------------------------------------------------------------------ #
    # File handling                                                        #
    # ------------------------------------------------------------------ #

    def _on_files_dropped(self, paths: List[str]):
        self._file_list.add_files(paths)
        self._set_status(f"{len(self._file_list.file_paths)} file(s) queued")

    def _update_process_btn(self):
        has_files  = bool(self._file_list.file_paths)
        has_fields = bool(self._field_selector.selected_fields())
        self._proc_btn.setEnabled(has_files and has_fields)

    # ------------------------------------------------------------------ #
    # Processing                                                           #
    # ------------------------------------------------------------------ #

    def _current_fmt(self) -> str:
        idx = self._fmt_combo.currentIndex()
        return _FORMATS[idx][1] if 0 <= idx < len(_FORMATS) else "csv"

    def _start_processing(self):
        files = self._file_list.file_paths
        filters = self._filter_panel.get_config()

        if not files:
            QMessageBox.warning(self, "No files", "Please add at least one XML file.")
            return
        if not self._field_selector.selected_fields():
            QMessageBox.warning(self, "No fields", "Please select at least one output field.")
            return

        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._prog_lbl.setVisible(True)
        self._prog_lbl.setText("Starting…")
        self._proc_btn.setEnabled(False)
        self._result_tabs.setVisible(False)
        self._set_status("Processing…")

        self._worker = _ProcessWorker(files, filters)
        self._worker.signals.progress.connect(self._on_file_progress)
        self._worker.signals.event_progress.connect(self._on_event_progress)
        self._worker.signals.finished.connect(self._on_finished)
        self._worker.signals.error.connect(self._on_error)
        self._worker.start()

    def _on_file_progress(self, current: int, total: int, msg: str):
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(current)
        self._progress_bar.setFormat("File %v/%m")
        self._prog_lbl.setText(msg)
        self._set_status(msg)

    def _on_event_progress(self, current: int, total: int, msg: str):
        self._set_status(msg)

    def _on_finished(self, results: list):
        self._results = results
        self._progress_bar.setValue(self._progress_bar.maximum())
        self._prog_lbl.setText(
            f"Done — {len(results)} event(s), "
            f"{sum(r.get('stationCount',0) for r in results)} records"
        )

        versions = sorted({r.get("schemaVersion", "?") for r in results})
        self._schema_lbl.setText(
            f"Schema: {', '.join(versions)}" if versions else ""
        )

        fmt    = self._current_fmt()
        fields = self._field_selector.selected_fields()
        self._results_panel.populate(results, fields, fmt)
        self._stats_panel.populate(results)
        self._result_tabs.setVisible(bool(results))

        self._proc_btn.setEnabled(True)
        self._set_status(
            f"Completed: {len(results)} events from {len(self._file_list.file_paths)} file(s)"
        )

    def _on_error(self, msg: str):
        self._progress_bar.setVisible(False)
        self._prog_lbl.setVisible(False)
        self._proc_btn.setEnabled(True)
        QMessageBox.critical(self, "Processing Error", msg)
        self._set_status(f"Error: {msg}")

    # ------------------------------------------------------------------ #
    # Presets                                                              #
    # ------------------------------------------------------------------ #

    def _refresh_preset_combo(self):
        self._preset_combo.clear()
        self._preset_combo.addItem("— select preset —")
        for path in list_presets():
            try:
                data = load_preset(path)
                self._preset_combo.addItem(
                    data.get("name", path.stem), userData=str(path)
                )
            except Exception:
                pass

    def _load_preset_from_combo(self):
        path_str = self._preset_combo.currentData()
        if not path_str:
            return
        try:
            data = load_preset(Path(path_str))
            self._apply_preset(data)
        except Exception as exc:
            QMessageBox.critical(self, "Preset error", str(exc))

    def _open_preset_manager(self):
        dlg = PresetDialog(
            self._filter_panel.get_config(),
            self._field_selector.selected_fields(),
            self._current_fmt(),
            parent=self,
        )
        dlg.preset_loaded.connect(self._apply_preset)
        dlg.exec_()
        self._refresh_preset_combo()

    def _apply_preset(self, data: dict):
        if "filters" in data:
            self._filter_panel.set_config(FilterConfig.from_dict(data["filters"]))
        if "fields" in data:
            self._field_selector.set_selected(data["fields"])
        if "format" in data:
            fmt = data["format"]
            for i, (_, val) in enumerate(_FORMATS):
                if val == fmt:
                    self._fmt_combo.setCurrentIndex(i)
                    break
        self._set_status(f"Preset '{data.get('name','?')}' loaded")

    # ------------------------------------------------------------------ #
    # Status bar                                                           #
    # ------------------------------------------------------------------ #

    def _set_status(self, msg: str):
        self._status_lbl.setText(msg)
