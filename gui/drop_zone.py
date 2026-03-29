"""
Drag-and-drop file zone widget.
"""
from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QDragEnterEvent, QDropEvent
from PyQt5.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QSizePolicy,
)


class DropZone(QFrame):
    """
    A dashed-border frame that accepts XML files via drag-and-drop
    or a click-to-browse action.

    Emits:
        files_dropped(list[str])  — absolute paths of the dropped/selected XML files
    """

    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("drop_zone")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(130)
        self._build_ui()
        self._set_idle_style()

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        self._icon_lbl = QLabel("📂", self)
        self._icon_lbl.setAlignment(Qt.AlignCenter)
        self._icon_lbl.setStyleSheet("font-size: 36px; border: none;")
        layout.addWidget(self._icon_lbl)

        self._title_lbl = QLabel("Drop SeisComP XML files here", self)
        self._title_lbl.setAlignment(Qt.AlignCenter)
        self._title_lbl.setStyleSheet(
            "font-size: 15px; font-weight: 600; border: none;"
        )
        layout.addWidget(self._title_lbl)

        self._sub_lbl = QLabel("or", self)
        self._sub_lbl.setAlignment(Qt.AlignCenter)
        self._sub_lbl.setStyleSheet(
            "font-size: 12px; color: #95a5a6; border: none;"
        )
        layout.addWidget(self._sub_lbl)

        browse_btn = QPushButton("Browse Files")
        browse_btn.setFixedWidth(130)
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.clicked.connect(self._browse)

        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)
        btn_row.addWidget(browse_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------ #
    # Style helpers                                                        #
    # ------------------------------------------------------------------ #

    def _set_idle_style(self):
        self.setStyleSheet(
            "QFrame#drop_zone {"
            "  border: 2px dashed #3498db;"
            "  border-radius: 12px;"
            "  background: transparent;"
            "}"
        )

    def _set_hover_style(self):
        self.setStyleSheet(
            "QFrame#drop_zone {"
            "  border: 2px dashed #27ae60;"
            "  border-radius: 12px;"
            "  background: rgba(39,174,96,0.07);"
            "}"
        )

    # ------------------------------------------------------------------ #
    # Drag / drop                                                          #
    # ------------------------------------------------------------------ #

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in event.mimeData().urls()]
            if any(p.lower().endswith(".xml") for p in paths):
                event.acceptProposedAction()
                self._set_hover_style()
                return
        event.ignore()

    def dragLeaveEvent(self, _):
        self._set_idle_style()

    def dropEvent(self, event: QDropEvent):
        self._set_idle_style()
        paths = [
            u.toLocalFile()
            for u in event.mimeData().urls()
            if u.toLocalFile().lower().endswith(".xml")
        ]
        if paths:
            self.files_dropped.emit(paths)

    # ------------------------------------------------------------------ #
    # Browse                                                               #
    # ------------------------------------------------------------------ #

    def _browse(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select SeisComP XML Files",
            "",
            "SeisComP XML (*.xml);;All Files (*)",
        )
        if paths:
            self.files_dropped.emit(paths)
