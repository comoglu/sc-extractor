"""
Preset management — save / load / delete named configurations.

Presets are stored as JSON files in ~/.sc_extractor/presets/.
Each file holds: name, filters (FilterConfig.to_dict), fields (list), format (str).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QLineEdit, QMessageBox,
    QDialogButtonBox, QInputDialog, QFileDialog,
)

from core.filters import FilterConfig
from core.presets import PRESETS_DIR, load_preset, save_preset, list_presets


# ──────────────────────────────────────────────────────────────────────────────
# Dialog
# ──────────────────────────────────────────────────────────────────────────────

class PresetDialog(QDialog):
    """
    Modal dialog for browsing, loading, saving, deleting,
    importing and exporting presets.

    Signals:
        preset_loaded(dict)   — emitted when the user clicks Load
    """

    preset_loaded = pyqtSignal(dict)

    def __init__(self, current_filters: FilterConfig,
                 current_fields: list[str], current_fmt: str,
                 parent=None):
        super().__init__(parent)
        self._filters = current_filters
        self._fields = current_fields
        self._fmt = current_fmt

        self.setWindowTitle("Preset Manager")
        self.setMinimumSize(460, 380)
        self._build_ui()
        self._refresh_list()

    # ------------------------------------------------------------------ #

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        lay.addWidget(QLabel("<b>Saved presets</b>"))

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.itemDoubleClicked.connect(self._load_selected)
        lay.addWidget(self._list, 1)

        # ── Action buttons ───────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self._load_btn = QPushButton("Load")
        self._load_btn.setObjectName("btn_success")
        self._load_btn.clicked.connect(self._load_selected)

        self._save_btn = QPushButton("Save current…")
        self._save_btn.clicked.connect(self._save_current)

        self._del_btn = QPushButton("Delete")
        self._del_btn.setObjectName("btn_danger")
        self._del_btn.clicked.connect(self._delete_selected)

        self._import_btn = QPushButton("Import…")
        self._import_btn.setObjectName("btn_secondary")
        self._import_btn.clicked.connect(self._import_preset)

        self._export_btn = QPushButton("Export…")
        self._export_btn.setObjectName("btn_secondary")
        self._export_btn.clicked.connect(self._export_selected)

        for b in (self._load_btn, self._save_btn, self._del_btn,
                  self._import_btn, self._export_btn):
            btn_row.addWidget(b)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn, alignment=Qt.AlignRight)

    # ------------------------------------------------------------------ #

    def _refresh_list(self):
        self._list.clear()
        for path in list_presets():
            try:
                data = load_preset(path)
                name = data.get("name", path.stem)
                fields_count = len(data.get("fields", []))
                item = QListWidgetItem(
                    f"{name}  —  {fields_count} fields  |  {data.get('format','?')}"
                )
                item.setData(Qt.UserRole, str(path))
                self._list.addItem(item)
            except Exception:
                pass

    def _selected_path(self) -> Optional[Path]:
        item = self._list.currentItem()
        if item is None:
            return None
        return Path(item.data(Qt.UserRole))

    def _load_selected(self):
        path = self._selected_path()
        if path is None:
            QMessageBox.warning(self, "No selection", "Please select a preset first.")
            return
        try:
            data = load_preset(path)
            self.preset_loaded.emit(data)
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Load error", str(exc))

    def _save_current(self):
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        safe = name.replace(" ", "_").replace("/", "_")
        path = PRESETS_DIR / f"{safe}.json"
        try:
            save_preset(path, name, self._filters, self._fields, self._fmt)
            self._refresh_list()
        except Exception as exc:
            QMessageBox.critical(self, "Save error", str(exc))

    def _delete_selected(self):
        path = self._selected_path()
        if path is None:
            return
        reply = QMessageBox.question(
            self, "Delete preset",
            f"Delete '{path.stem}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            path.unlink(missing_ok=True)
            self._refresh_list()

    def _import_preset(self):
        src, _ = QFileDialog.getOpenFileName(
            self, "Import preset", "", "JSON preset (*.json)"
        )
        if not src:
            return
        dst = PRESETS_DIR / Path(src).name
        dst.write_bytes(Path(src).read_bytes())
        self._refresh_list()

    def _export_selected(self):
        path = self._selected_path()
        if path is None:
            QMessageBox.warning(self, "No selection", "Please select a preset first.")
            return
        dst, _ = QFileDialog.getSaveFileName(
            self, "Export preset", path.name, "JSON preset (*.json)"
        )
        if dst:
            Path(dst).write_bytes(path.read_bytes())
