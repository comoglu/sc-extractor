"""
Results panel — shown after a successful processing run.
Displays per-event stats and download buttons for individual files or a bulk ZIP.
Extended format downloads (HYPO71, Nordic, SQLite, Parquet) offered as single-file exports.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import List, Dict, Any

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QFileDialog, QSizePolicy,
)

from core.exporters import (
    generate_csv, generate_geojson, export_to_zip, export_single_event,
    sanitize_filename,
)


class _EventCard(QFrame):
    """Compact card for a single event with CSV / GeoJSON download."""

    download_csv     = pyqtSignal(dict)
    download_geojson = pyqtSignal(dict)

    def __init__(self, result: Dict[str, Any], fmt: str, parent=None):
        super().__init__(parent)
        self._result = result
        self._fmt    = fmt

        self.setObjectName("card")
        self.setFrameShape(QFrame.StyledPanel)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        info = QVBoxLayout()
        info.setSpacing(2)
        eid_lbl = QLabel(f"<b>{result.get('eventId','?')}</b>")
        eid_lbl.setTextFormat(Qt.RichText)
        info.addWidget(eid_lbl)

        meta_lbl = QLabel(
            f"{result.get('stationCount',0)} records  |  "
            f"schema {result.get('schemaVersion','?')}  |  "
            f"{result.get('fileName','')}"
        )
        meta_lbl.setStyleSheet("font-size: 11px; color: #7f8c8d;")
        info.addWidget(meta_lbl)
        lay.addLayout(info, 1)

        if fmt in ("csv", "both"):
            btn = QPushButton("⬇ CSV")
            btn.setFixedSize(80, 28)
            btn.setObjectName("btn_success")
            btn.setToolTip("Save this event as CSV")
            btn.clicked.connect(lambda: self.download_csv.emit(result))
            lay.addWidget(btn)

        if fmt in ("geojson", "both"):
            btn = QPushButton("⬇ GeoJSON")
            btn.setFixedSize(96, 28)
            btn.setObjectName("btn_warning")
            btn.setToolTip("Save this event as GeoJSON")
            btn.clicked.connect(lambda: self.download_geojson.emit(result))
            lay.addWidget(btn)


# ──────────────────────────────────────────────────────────────────────────────

class ResultsPanel(QWidget):
    """Summary banner + bulk download + scrollable per-event cards."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: List[Dict] = []
        self._fields:  List[str] = []
        self._fmt = "csv"
        self._build_ui()

    # ------------------------------------------------------------------ #

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Summary banner
        self._banner = QFrame()
        self._banner.setObjectName("card")
        ban_lay = QVBoxLayout(self._banner)
        ban_lay.setContentsMargins(16, 12, 16, 12)
        ban_lay.setSpacing(8)

        self._summary_lbl = QLabel()
        self._summary_lbl.setTextFormat(Qt.RichText)
        ban_lay.addWidget(self._summary_lbl)

        # Download row
        dl_row = QHBoxLayout()
        dl_row.setSpacing(8)

        self._zip_csv_btn = QPushButton("📦 All CSV (ZIP)")
        self._zip_csv_btn.setObjectName("btn_success")
        self._zip_csv_btn.clicked.connect(lambda: self._download_zip("csv"))
        dl_row.addWidget(self._zip_csv_btn)

        self._zip_gj_btn = QPushButton("🗺 All GeoJSON (ZIP)")
        self._zip_gj_btn.setObjectName("btn_warning")
        self._zip_gj_btn.clicked.connect(lambda: self._download_zip("geojson"))
        dl_row.addWidget(self._zip_gj_btn)

        self._zip_both_btn = QPushButton("📂 All CSV+GeoJSON (ZIP)")
        self._zip_both_btn.clicked.connect(lambda: self._download_zip("both"))
        dl_row.addWidget(self._zip_both_btn)

        # Extended format download buttons (single-file whole-catalog exports)
        self._hypo71_btn = QPushButton("⬇ HYPO71 (.pha)")
        self._hypo71_btn.clicked.connect(self._download_hypo71)
        dl_row.addWidget(self._hypo71_btn)

        self._nordic_btn = QPushButton("⬇ Nordic (.nor)")
        self._nordic_btn.clicked.connect(self._download_nordic)
        dl_row.addWidget(self._nordic_btn)

        self._sqlite_btn = QPushButton("⬇ SQLite (.db)")
        self._sqlite_btn.clicked.connect(self._download_sqlite)
        dl_row.addWidget(self._sqlite_btn)

        self._parquet_btn = QPushButton("⬇ Parquet")
        self._parquet_btn.clicked.connect(self._download_parquet)
        dl_row.addWidget(self._parquet_btn)

        dl_row.addStretch()
        ban_lay.addLayout(dl_row)
        layout.addWidget(self._banner)

        # Per-event list
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch()

        self._scroll.setWidget(self._list_widget)
        layout.addWidget(self._scroll, 1)

    # ------------------------------------------------------------------ #

    def populate(self, results: List[Dict], selected_fields: List[str], fmt: str):
        self._results = results
        self._fields  = selected_fields
        self._fmt     = fmt

        total_records = sum(r.get("stationCount", 0) for r in results)
        self._summary_lbl.setText(
            f"<b>{len(results)}</b> events &nbsp;|&nbsp; "
            f"<b>{total_records}</b> records &nbsp;|&nbsp; "
            f"<b>{len(selected_fields)}</b> fields &nbsp;|&nbsp; "
            f"format: <b>{fmt}</b>"
        )

        # ZIP buttons only for csv/geojson/both
        csv_geo = fmt in ("csv", "geojson", "both")
        self._zip_csv_btn.setVisible(fmt in ("csv", "both"))
        self._zip_gj_btn.setVisible(fmt in ("geojson", "both"))
        self._zip_both_btn.setVisible(fmt == "both")
        # Extended format buttons always shown (allow post-hoc export)
        self._hypo71_btn.setVisible(True)
        self._nordic_btn.setVisible(True)
        self._sqlite_btn.setVisible(True)
        self._parquet_btn.setVisible(True)

        # Rebuild per-event cards (only meaningful for csv/geojson)
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if fmt in ("csv", "geojson", "both"):
            for result in results:
                card = _EventCard(result, fmt)
                card.download_csv.connect(self._on_download_csv)
                card.download_geojson.connect(self._on_download_geojson)
                self._list_layout.insertWidget(self._list_layout.count() - 1, card)

    # ------------------------------------------------------------------ #

    def _on_download_csv(self, result: Dict):
        self._save_event(result, "csv")

    def _on_download_geojson(self, result: Dict):
        self._save_event(result, "geojson")

    def _save_event(self, result: Dict, fmt: str):
        eid = sanitize_filename(result.get("eventId", "event"))
        ext = "csv" if fmt == "csv" else "geojson"
        path, _ = QFileDialog.getSaveFileName(
            self, f"Save {fmt.upper()}", f"{eid}_stations.{ext}",
            "CSV (*.csv)" if fmt == "csv" else "GeoJSON (*.geojson)",
        )
        if not path:
            return
        created = export_single_event(result, Path(path).parent, fmt, self._fields)
        if created:
            created[0].rename(path)

    def _download_zip(self, fmt: str):
        if not self._results:
            return
        today = date.today().isoformat()
        default = f"seiscomp_{today}_{fmt}_{len(self._results)}events.zip"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save ZIP archive", default, "ZIP archive (*.zip)"
        )
        if path:
            export_to_zip(self._results, path, fmt, self._fields)

    def _download_hypo71(self):
        if not self._results:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save HYPO71 phase file",
            f"seiscomp_{date.today().isoformat()}.pha",
            "HYPO71 phase file (*.pha);;All files (*)",
        )
        if path:
            from core.formats import generate_hypo71
            Path(path).write_text(generate_hypo71(self._results), encoding="utf-8")

    def _download_nordic(self):
        if not self._results:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Nordic/SEISAN file",
            f"seiscomp_{date.today().isoformat()}.nor",
            "Nordic file (*.nor);;All files (*)",
        )
        if path:
            from core.formats import generate_nordic
            Path(path).write_text(generate_nordic(self._results), encoding="utf-8")

    def _download_sqlite(self):
        if not self._results:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save SQLite database",
            f"seiscomp_{date.today().isoformat()}.db",
            "SQLite database (*.db);;All files (*)",
        )
        if path:
            from core.formats import export_to_sqlite
            export_to_sqlite(self._results, path, self._fields)

    def _download_parquet(self):
        if not self._results:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Parquet file",
            f"seiscomp_{date.today().isoformat()}.parquet",
            "Parquet (*.parquet);;All files (*)",
        )
        if path:
            try:
                from core.formats import export_to_parquet
                export_to_parquet(self._results, path, self._fields)
            except ImportError as exc:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Missing dependency", str(exc))
