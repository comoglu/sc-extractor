"""
Qt stylesheet definitions — light and dark themes.
"""

LIGHT = """
QMainWindow, QDialog {
    background: #f0f2f5;
}
QWidget {
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    font-size: 13px;
    color: #2c3e50;
}
/* ── Panels ──────────────────────────────── */
QFrame#card {
    background: #ffffff;
    border: 1px solid #dde3ea;
    border-radius: 10px;
}
/* ── Section labels ──────────────────────── */
QLabel#section_title {
    font-size: 15px;
    font-weight: 600;
    color: #2c3e50;
    padding-bottom: 4px;
}
/* ── Buttons ─────────────────────────────── */
QPushButton {
    background: #3498db;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton:hover    { background: #2980b9; }
QPushButton:pressed  { background: #2471a3; }
QPushButton:disabled { background: #bdc3c7; color: #7f8c8d; }

QPushButton#btn_success {
    background: #27ae60;
}
QPushButton#btn_success:hover { background: #229954; }

QPushButton#btn_warning {
    background: #e67e22;
}
QPushButton#btn_warning:hover { background: #d35400; }

QPushButton#btn_danger {
    background: #e74c3c;
}
QPushButton#btn_danger:hover { background: #c0392b; }

QPushButton#btn_secondary {
    background: #7f8c8d;
}
QPushButton#btn_secondary:hover { background: #636e72; }

QPushButton#btn_process {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #2c3e50, stop:1 #4a6741);
    color: white;
    font-size: 15px;
    font-weight: 700;
    padding: 12px 28px;
    border-radius: 8px;
}
QPushButton#btn_process:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #1a252f, stop:1 #3a5231);
}
QPushButton#btn_process:disabled {
    background: #bdc3c7;
}
/* ── Inputs ──────────────────────────────── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #ffffff;
    border: 1px solid #ccd1d9;
    border-radius: 5px;
    padding: 5px 9px;
    font-size: 13px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #3498db;
}
QComboBox::drop-down { border: none; padding-right: 6px; }
/* ── Progress bar ────────────────────────── */
QProgressBar {
    border: 1px solid #dde3ea;
    border-radius: 6px;
    background: #ecf0f1;
    height: 20px;
    text-align: center;
    font-weight: 600;
    font-size: 12px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #3498db, stop:1 #27ae60);
    border-radius: 5px;
}
/* ── Checkboxes ──────────────────────────── */
QCheckBox {
    spacing: 6px;
    font-size: 13px;
}
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #95a5a6;
    border-radius: 3px;
    background: white;
}
QCheckBox::indicator:checked {
    background: #3498db;
    border-color: #3498db;
    image: url(none);
}
/* ── Scroll areas ────────────────────────── */
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    width: 8px; background: #f0f2f5; border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #bdc3c7; border-radius: 4px; min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #95a5a6; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
/* ── Group box (category headers) ────────── */
QGroupBox {
    border: 1px solid #dde3ea;
    border-radius: 7px;
    margin-top: 8px;
    font-weight: 600;
    font-size: 12px;
    padding-top: 14px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 10px;
    color: #2c3e50;
}
/* ── Tab widget ──────────────────────────── */
QTabWidget::pane {
    border: 1px solid #dde3ea;
    border-radius: 0 8px 8px 8px;
    background: #ffffff;
}
QTabBar::tab {
    background: #ecf0f1;
    border: 1px solid #dde3ea;
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    padding: 7px 18px;
    font-weight: 600;
    margin-right: 2px;
}
QTabBar::tab:selected { background: #ffffff; color: #3498db; }
QTabBar::tab:hover    { background: #d6eaf8; }
/* ── List widget ─────────────────────────── */
QListWidget {
    border: 1px solid #dde3ea;
    border-radius: 6px;
    background: #ffffff;
    font-size: 13px;
}
QListWidget::item { padding: 6px 10px; }
QListWidget::item:selected { background: #d6eaf8; color: #2c3e50; }
QListWidget::item:hover    { background: #eaf4fb; }
/* ── Separator ───────────────────────────── */
QFrame[frameShape="4"], QFrame[frameShape="5"] {
    color: #dde3ea;
}
/* ── Tool bar ────────────────────────────── */
QToolBar {
    background: #2c3e50;
    border: none;
    padding: 4px 8px;
    spacing: 6px;
}
QToolBar QLabel { color: #ecf0f1; font-weight: 600; }
QToolBar QPushButton {
    background: rgba(255,255,255,0.15);
    border: 1px solid rgba(255,255,255,0.25);
    border-radius: 5px;
    padding: 5px 12px;
    color: white;
    font-size: 12px;
}
QToolBar QPushButton:hover  { background: rgba(255,255,255,0.25); }
QToolBar QComboBox {
    background: rgba(255,255,255,0.15);
    border: 1px solid rgba(255,255,255,0.3);
    border-radius: 5px;
    color: white;
    padding: 4px 8px;
    min-width: 150px;
}
QToolBar QComboBox QAbstractItemView {
    background: #2c3e50;
    color: white;
    selection-background-color: #3498db;
}
/* ── Status bar ──────────────────────────── */
QStatusBar { background: #2c3e50; color: #ecf0f1; font-size: 12px; }
/* ── Tooltips ────────────────────────────── */
QToolTip {
    background: #2c3e50;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}
/* ── Search box ──────────────────────────── */
QLineEdit#search_box {
    background: #ecf0f1;
    border: 1px solid #bdc3c7;
    border-radius: 14px;
    padding: 5px 12px;
    font-size: 13px;
}
QLineEdit#search_box:focus { border-color: #3498db; background: white; }
"""

DARK = """
QMainWindow, QDialog {
    background: #1a1d23;
}
QWidget {
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    font-size: 13px;
    color: #dfe6e9;
}
QFrame#card {
    background: #232730;
    border: 1px solid #2f3542;
    border-radius: 10px;
}
QLabel#section_title {
    font-size: 15px;
    font-weight: 600;
    color: #74b9ff;
    padding-bottom: 4px;
}
QPushButton {
    background: #2980b9;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 600;
}
QPushButton:hover    { background: #3498db; }
QPushButton:pressed  { background: #2471a3; }
QPushButton:disabled { background: #2f3542; color: #636e72; }

QPushButton#btn_success { background: #00b894; }
QPushButton#btn_success:hover { background: #00cec9; }

QPushButton#btn_warning { background: #e17055; }
QPushButton#btn_warning:hover { background: #d63031; }

QPushButton#btn_danger { background: #d63031; }
QPushButton#btn_danger:hover { background: #c0392b; }

QPushButton#btn_secondary { background: #636e72; }
QPushButton#btn_secondary:hover { background: #74b9ff; }

QPushButton#btn_process {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #0984e3, stop:1 #00b894);
    color: white;
    font-size: 15px;
    font-weight: 700;
    padding: 12px 28px;
    border-radius: 8px;
}
QPushButton#btn_process:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #74b9ff, stop:1 #00cec9);
}
QPushButton#btn_process:disabled { background: #2f3542; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #2f3542;
    border: 1px solid #404755;
    border-radius: 5px;
    padding: 5px 9px;
    color: #dfe6e9;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #74b9ff;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background: #2f3542;
    color: #dfe6e9;
    selection-background-color: #0984e3;
}

QProgressBar {
    border: 1px solid #2f3542;
    border-radius: 6px;
    background: #2f3542;
    height: 20px;
    text-align: center;
    font-weight: 600;
    font-size: 12px;
    color: white;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #0984e3, stop:1 #00b894);
    border-radius: 5px;
}

QCheckBox { spacing: 6px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #636e72;
    border-radius: 3px;
    background: #2f3542;
}
QCheckBox::indicator:checked {
    background: #0984e3;
    border-color: #0984e3;
}

QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    width: 8px; background: #1a1d23; border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #404755; border-radius: 4px; min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #636e72; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QGroupBox {
    border: 1px solid #2f3542;
    border-radius: 7px;
    margin-top: 8px;
    font-weight: 600;
    font-size: 12px;
    padding-top: 14px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 10px;
    color: #74b9ff;
}

QTabWidget::pane {
    border: 1px solid #2f3542;
    border-radius: 0 8px 8px 8px;
    background: #232730;
}
QTabBar::tab {
    background: #1a1d23;
    border: 1px solid #2f3542;
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    padding: 7px 18px;
    font-weight: 600;
    margin-right: 2px;
    color: #b2bec3;
}
QTabBar::tab:selected { background: #232730; color: #74b9ff; }
QTabBar::tab:hover    { background: #2f3542; }

QListWidget {
    border: 1px solid #2f3542;
    border-radius: 6px;
    background: #232730;
}
QListWidget::item { padding: 6px 10px; color: #dfe6e9; }
QListWidget::item:selected { background: #0984e3; color: white; }
QListWidget::item:hover    { background: #2f3542; }

QFrame[frameShape="4"], QFrame[frameShape="5"] { color: #2f3542; }

QToolBar {
    background: #141720;
    border: none;
    padding: 4px 8px;
    spacing: 6px;
}
QToolBar QLabel { color: #74b9ff; font-weight: 600; }
QToolBar QPushButton {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 5px;
    padding: 5px 12px;
    color: #dfe6e9;
    font-size: 12px;
}
QToolBar QPushButton:hover { background: rgba(255,255,255,0.15); }
QToolBar QComboBox {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 5px;
    color: #dfe6e9;
    padding: 4px 8px;
    min-width: 150px;
}

QStatusBar { background: #141720; color: #74b9ff; font-size: 12px; }

QToolTip {
    background: #2f3542;
    color: #dfe6e9;
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
}

QLineEdit#search_box {
    background: #2f3542;
    border: 1px solid #404755;
    border-radius: 14px;
    padding: 5px 12px;
}
QLineEdit#search_box:focus { border-color: #74b9ff; background: #3a4055; }
"""
