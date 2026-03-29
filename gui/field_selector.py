"""
Field-selection panel: collapsible category groups with checkboxes,
a live search filter, and Select-All / Deselect-All / Recommended shortcuts.
"""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal, QSortFilterProxyModel
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QPushButton, QCheckBox, QLabel, QLineEdit, QGridLayout,
    QSizePolicy, QToolButton,
)

from core.fields import FIELD_CATEGORIES, RECOMMENDED_FIELDS


class _CategoryHeader(QFrame):
    """Clickable header that toggles the category body open/closed."""

    toggled = pyqtSignal(bool)

    def __init__(self, title: str, color: str, parent=None):
        super().__init__(parent)
        self.setObjectName("cat_header")
        self._open = True
        self._color = color

        self.setStyleSheet(
            f"QFrame#cat_header {{"
            f"  background: {color};"
            f"  border-radius: 6px;"
            f"  padding: 2px;"
            f"}}"
        )
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)

        # Collapse arrow
        self._arrow = QLabel("▼")
        self._arrow.setStyleSheet(
            "color: white; font-size: 11px; border: none; background: transparent;"
        )
        lay.addWidget(self._arrow)

        lbl = QLabel(title)
        lbl.setStyleSheet(
            "color: white; font-weight: 700; font-size: 13px;"
            " border: none; background: transparent;"
        )
        lay.addWidget(lbl, 1)

        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(
            "color: rgba(255,255,255,0.75); font-size: 11px;"
            " border: none; background: transparent;"
        )
        lay.addWidget(self._count_lbl)

    def mousePressEvent(self, _):
        self._open = not self._open
        self._arrow.setText("▼" if self._open else "▶")
        self.toggled.emit(self._open)

    def set_count(self, selected: int, total: int):
        self._count_lbl.setText(f"{selected}/{total}")


class _CategoryWidget(QWidget):
    """One expandable category containing a grid of checkboxes."""

    selection_changed = pyqtSignal()

    def __init__(self, name: str, fields: dict[str, str], color: str, parent=None):
        super().__init__(parent)
        self._fields = fields      # key → label
        self._boxes: dict[str, QCheckBox] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 6)
        outer.setSpacing(0)

        self._header = _CategoryHeader(name, color)
        outer.addWidget(self._header)

        # Body
        self._body = QFrame()
        self._body.setObjectName("cat_body")
        self._body.setStyleSheet(
            "QFrame#cat_body {"
            "  border: 1px solid #dde3ea;"
            "  border-top: none;"
            "  border-radius: 0 0 6px 6px;"
            "  background: transparent;"
            "}"
        )
        body_lay = QVBoxLayout(self._body)
        body_lay.setContentsMargins(8, 6, 8, 8)
        body_lay.setSpacing(2)

        # Cat-level select-all / deselect-all row
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(4)
        for label, action in (("All", self._select_all), ("None", self._deselect_all)):
            b = QPushButton(label)
            b.setFixedSize(48, 22)
            b.setStyleSheet(
                f"QPushButton {{ background: {color}; color: white;"
                " border-radius: 4px; font-size: 11px; font-weight:600;"
                " padding: 0; }}"
                f"QPushButton:hover {{ border: 1px solid white; }}"
            )
            b.clicked.connect(action)
            ctrl_row.addWidget(b)
        ctrl_row.addStretch()
        body_lay.addLayout(ctrl_row)

        # Checkbox grid
        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(4)
        self._grid.setVerticalSpacing(2)
        body_lay.addLayout(self._grid)

        self._populate_grid()
        outer.addWidget(self._body)

        self._header.toggled.connect(self._body.setVisible)
        self._update_header_count()

    # ------------------------------------------------------------------ #

    def _populate_grid(self, filter_text: str = ""):
        # Clear existing widgets
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        col = 0
        row = 0
        max_cols = 2
        ft = filter_text.lower()

        for key, label in self._fields.items():
            if ft and ft not in label.lower() and ft not in key.lower():
                continue

            cb = self._boxes.get(key)
            if cb is None:
                cb = QCheckBox(label)
                cb.setChecked(key in RECOMMENDED_FIELDS)
                cb.stateChanged.connect(self._on_change)
                self._boxes[key] = cb

            self._grid.addWidget(cb, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def apply_filter(self, text: str):
        self._populate_grid(text)

    def _on_change(self):
        self._update_header_count()
        self.selection_changed.emit()

    def _update_header_count(self):
        visible = [k for k in self._boxes if self._boxes[k].isVisible()]
        total = len(self._fields)
        sel = sum(1 for cb in self._boxes.values() if cb.isChecked())
        self._header.set_count(sel, total)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def selected_fields(self) -> list[str]:
        return [k for k, cb in self._boxes.items() if cb.isChecked()]

    def set_selected(self, keys: list[str]):
        for k, cb in self._boxes.items():
            cb.blockSignals(True)
            cb.setChecked(k in keys)
            cb.blockSignals(False)
        self._update_header_count()
        self.selection_changed.emit()

    def _select_all(self):
        for cb in self._boxes.values():
            cb.blockSignals(True)
            cb.setChecked(True)
            cb.blockSignals(False)
        self._update_header_count()
        self.selection_changed.emit()

    def _deselect_all(self):
        for cb in self._boxes.values():
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
        self._update_header_count()
        self.selection_changed.emit()


# ──────────────────────────────────────────────────────────────────────────────
# Main widget
# ──────────────────────────────────────────────────────────────────────────────

class FieldSelector(QWidget):
    """
    Scrollable field-selector panel with per-category collapsible groups,
    a search bar, and global control buttons.

    Emits:
        selection_changed()   whenever the set of selected fields changes
    """

    selection_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._categories: list[_CategoryWidget] = []
        self._build_ui()
        self._populate_categories()

    # ------------------------------------------------------------------ #

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # — Search bar ——————————————————
        self._search = QLineEdit()
        self._search.setObjectName("search_box")
        self._search.setPlaceholderText("🔍  Search fields…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search)
        layout.addWidget(self._search)

        # — Global buttons ——————————————
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        for label, obj_name, slot in (
            ("✓ Select All",    "btn_success",   self.select_all),
            ("✗ Deselect All",  "btn_secondary", self.deselect_all),
            ("⭐ Recommended",  "btn_warning",   self.select_recommended),
            ("⊟ Collapse All",  None,            self._collapse_all),
        ):
            b = QPushButton(label)
            if obj_name:
                b.setObjectName(obj_name)
            b.setFixedHeight(30)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        # — Field count label ———————————
        self._count_lbl = QLabel()
        self._count_lbl.setStyleSheet("font-size: 12px; color: #7f8c8d;")
        layout.addWidget(self._count_lbl)

        # — Scroll area ————————————————
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._scroll_widget = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_widget)
        self._scroll_layout.setContentsMargins(2, 2, 2, 2)
        self._scroll_layout.setSpacing(4)
        self._scroll_layout.addStretch()

        self._scroll.setWidget(self._scroll_widget)
        layout.addWidget(self._scroll, 1)

    # ------------------------------------------------------------------ #

    def _populate_categories(self):
        stretch = self._scroll_layout.takeAt(self._scroll_layout.count() - 1)

        for cat_name, cat_data in FIELD_CATEGORIES.items():
            widget = _CategoryWidget(
                cat_name, cat_data["fields"], cat_data["color"]
            )
            widget.selection_changed.connect(self._on_selection_changed)
            self._categories.append(widget)
            self._scroll_layout.addWidget(widget)

        self._scroll_layout.addStretch()
        self._update_count_label()

    # ------------------------------------------------------------------ #

    def _on_search(self, text: str):
        for cat in self._categories:
            cat.apply_filter(text)

    def _on_selection_changed(self):
        self._update_count_label()
        self.selection_changed.emit()

    def _update_count_label(self):
        sel = len(self.selected_fields())
        total = sum(len(c["fields"]) for c in FIELD_CATEGORIES.values())
        self._count_lbl.setText(f"{sel} of {total} fields selected")

    def _collapse_all(self):
        for cat in self._categories:
            cat._header._open = False
            cat._header._arrow.setText("▶")
            cat._body.setVisible(False)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def selected_fields(self) -> list[str]:
        result = []
        for cat in self._categories:
            result.extend(cat.selected_fields())
        return result

    def set_selected(self, keys: list[str]):
        for cat in self._categories:
            cat.set_selected(keys)
        self._update_count_label()

    def select_all(self):
        from core.fields import ALL_FIELDS
        self.set_selected(list(ALL_FIELDS.keys()))

    def deselect_all(self):
        self.set_selected([])

    def select_recommended(self):
        self.set_selected(RECOMMENDED_FIELDS)
