"""
Filter panel widget — tabbed UI exposing all FilterConfig settings.

Tabs:
  Basic    — arrival usage, magnitude, distance, phase
  Spatial  — bounding box / radius
  Temporal — start / end time
  Quality  — azimuthal gap, used phases, RMS, depth uncertainty
"""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QFormLayout, QHBoxLayout, QVBoxLayout,
    QLabel, QDoubleSpinBox, QSpinBox, QComboBox,
    QLineEdit, QTabWidget, QGroupBox,
)

from core.filters import FilterConfig


class FilterPanel(QWidget):
    """Tabbed filter configuration panel."""

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    # ------------------------------------------------------------------ #

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        outer.addWidget(self._tabs)

        self._tabs.addTab(self._build_basic_tab(),    "Basic")
        self._tabs.addTab(self._build_spatial_tab(),  "Spatial")
        self._tabs.addTab(self._build_temporal_tab(), "Temporal")
        self._tabs.addTab(self._build_quality_tab(),  "Quality")

    # ── Tab builders ─────────────────────────────────────────────────── #

    def _build_basic_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        # Arrival usage
        self._arrivals_combo = QComboBox()
        self._arrivals_combo.addItems([
            "All arrivals",
            "Used arrivals only",
            "Unused arrivals only",
        ])
        self._arrivals_combo.setToolTip(
            "Filter arrivals by the <b>timeUsed</b> flag set during location."
        )
        self._arrivals_combo.currentIndexChanged.connect(self.changed)
        form.addRow("Arrival usage:", self._arrivals_combo)

        # Min magnitude
        self._min_mag = QDoubleSpinBox()
        self._min_mag.setRange(0.0, 10.0)
        self._min_mag.setSingleStep(0.1)
        self._min_mag.setDecimals(1)
        self._min_mag.setValue(0.0)
        self._min_mag.setSpecialValueText("No filter")
        self._min_mag.setToolTip("Skip events with magnitude below this value.")
        self._min_mag.valueChanged.connect(self.changed)
        form.addRow("Min magnitude:", self._min_mag)

        # Max magnitude
        self._max_mag = QDoubleSpinBox()
        self._max_mag.setRange(0.0, 10.0)
        self._max_mag.setSingleStep(0.1)
        self._max_mag.setDecimals(1)
        self._max_mag.setValue(0.0)
        self._max_mag.setSpecialValueText("No filter")
        self._max_mag.setToolTip("Skip events with magnitude above this value.")
        self._max_mag.valueChanged.connect(self.changed)
        form.addRow("Max magnitude:", self._max_mag)

        # Max distance (°)
        self._max_dist = QDoubleSpinBox()
        self._max_dist.setRange(0.0, 180.0)
        self._max_dist.setSingleStep(1.0)
        self._max_dist.setDecimals(1)
        self._max_dist.setValue(0.0)
        self._max_dist.setSpecialValueText("No filter")
        self._max_dist.setToolTip("Skip arrivals beyond this epicentral distance (°).")
        self._max_dist.valueChanged.connect(self.changed)
        form.addRow("Max distance (°):", self._max_dist)

        # Phase filter
        phase_row = QHBoxLayout()
        phase_row.setSpacing(6)
        self._phase_combo = QComboBox()
        self._phase_combo.addItems([
            "All phases", "P phases only", "S phases only",
            "P and S only", "Custom…",
        ])
        self._phase_combo.currentIndexChanged.connect(self._on_phase_combo)
        phase_row.addWidget(self._phase_combo)
        self._phase_custom = QLineEdit()
        self._phase_custom.setPlaceholderText("e.g. P,Pg,S")
        self._phase_custom.setVisible(False)
        self._phase_custom.textChanged.connect(self.changed)
        phase_row.addWidget(self._phase_custom, 1)
        form.addRow("Phase filter:", phase_row)

        return w

    def _build_spatial_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(8)

        # Bounding box
        bbox_box = QGroupBox("Bounding Box  (leave 0/0 to disable)")
        bbox_form = QFormLayout(bbox_box)
        bbox_form.setSpacing(6)

        def _spin(lo, hi, tip):
            sb = QDoubleSpinBox()
            sb.setRange(lo, hi)
            sb.setSingleStep(1.0)
            sb.setDecimals(3)
            sb.setValue(0.0)
            sb.setSpecialValueText("—")
            sb.setToolTip(tip)
            sb.valueChanged.connect(self.changed)
            return sb

        self._bbox_lat_min = _spin(-90, 90,   "Minimum latitude (°)")
        self._bbox_lat_max = _spin(-90, 90,   "Maximum latitude (°)")
        self._bbox_lon_min = _spin(-180, 180, "Minimum longitude (°)")
        self._bbox_lon_max = _spin(-180, 180, "Maximum longitude (°)")

        bbox_form.addRow("Lat min (°):", self._bbox_lat_min)
        bbox_form.addRow("Lat max (°):", self._bbox_lat_max)
        bbox_form.addRow("Lon min (°):", self._bbox_lon_min)
        bbox_form.addRow("Lon max (°):", self._bbox_lon_max)
        outer.addWidget(bbox_box)

        # Radius
        rad_box = QGroupBox("Radius Filter")
        rad_form = QFormLayout(rad_box)
        rad_form.setSpacing(6)

        self._center_lat = QDoubleSpinBox()
        self._center_lat.setRange(-90, 90)
        self._center_lat.setDecimals(4)
        self._center_lat.setSingleStep(0.1)
        self._center_lat.setValue(0.0)
        self._center_lat.valueChanged.connect(self.changed)

        self._center_lon = QDoubleSpinBox()
        self._center_lon.setRange(-180, 180)
        self._center_lon.setDecimals(4)
        self._center_lon.setSingleStep(0.1)
        self._center_lon.setValue(0.0)
        self._center_lon.valueChanged.connect(self.changed)

        self._radius_km = QDoubleSpinBox()
        self._radius_km.setRange(0.0, 20000.0)
        self._radius_km.setDecimals(1)
        self._radius_km.setSingleStep(10.0)
        self._radius_km.setValue(0.0)
        self._radius_km.setSpecialValueText("No filter")
        self._radius_km.valueChanged.connect(self.changed)

        rad_form.addRow("Center lat (°):", self._center_lat)
        rad_form.addRow("Center lon (°):", self._center_lon)
        rad_form.addRow("Radius (km):",    self._radius_km)
        outer.addWidget(rad_box)
        outer.addStretch()

        return w

    def _build_temporal_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(6, 6, 6, 6)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._start_time = QLineEdit()
        self._start_time.setPlaceholderText("YYYY-MM-DDTHH:MM:SS  (blank = no filter)")
        self._start_time.setToolTip("Exclude events before this UTC time.")
        self._start_time.textChanged.connect(self.changed)
        form.addRow("Start time (UTC):", self._start_time)

        self._end_time = QLineEdit()
        self._end_time.setPlaceholderText("YYYY-MM-DDTHH:MM:SS  (blank = no filter)")
        self._end_time.setToolTip("Exclude events after this UTC time.")
        self._end_time.textChanged.connect(self.changed)
        form.addRow("End time (UTC):", self._end_time)

        return w

    def _build_quality_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(6, 6, 6, 6)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._max_gap = QDoubleSpinBox()
        self._max_gap.setRange(0.0, 360.0)
        self._max_gap.setSingleStep(10.0)
        self._max_gap.setDecimals(1)
        self._max_gap.setValue(0.0)
        self._max_gap.setSpecialValueText("No filter")
        self._max_gap.setToolTip("Skip events with azimuthal gap above this value (°).")
        self._max_gap.valueChanged.connect(self.changed)
        form.addRow("Max azimuthal gap (°):", self._max_gap)

        self._min_phases = QSpinBox()
        self._min_phases.setRange(0, 999)
        self._min_phases.setValue(0)
        self._min_phases.setSpecialValueText("No filter")
        self._min_phases.setToolTip("Skip events with fewer used phases than this.")
        self._min_phases.valueChanged.connect(self.changed)
        form.addRow("Min used phases:", self._min_phases)

        self._max_rms = QDoubleSpinBox()
        self._max_rms.setRange(0.0, 10.0)
        self._max_rms.setSingleStep(0.1)
        self._max_rms.setDecimals(2)
        self._max_rms.setValue(0.0)
        self._max_rms.setSpecialValueText("No filter")
        self._max_rms.setToolTip("Skip events with RMS residual above this value (s).")
        self._max_rms.valueChanged.connect(self.changed)
        form.addRow("Max RMS (s):", self._max_rms)

        self._max_dep_unc = QDoubleSpinBox()
        self._max_dep_unc.setRange(0.0, 500.0)
        self._max_dep_unc.setSingleStep(5.0)
        self._max_dep_unc.setDecimals(1)
        self._max_dep_unc.setValue(0.0)
        self._max_dep_unc.setSpecialValueText("No filter")
        self._max_dep_unc.setToolTip("Skip events with depth uncertainty above this value (km).")
        self._max_dep_unc.valueChanged.connect(self.changed)
        form.addRow("Max depth unc. (km):", self._max_dep_unc)

        return w

    # ------------------------------------------------------------------ #

    def _on_phase_combo(self, index: int):
        self._phase_custom.setVisible(index == 4)
        self.changed.emit()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def get_config(self) -> FilterConfig:
        # Basic
        idx     = self._arrivals_combo.currentIndex()
        arrivals = ("all", "used", "unused")[idx]
        min_mag  = self._min_mag.value() if self._min_mag.value() > 0.0 else None
        max_mag  = self._max_mag.value() if self._max_mag.value() > 0.0 else None
        max_dist = self._max_dist.value() if self._max_dist.value() > 0.0 else None

        pi = self._phase_combo.currentIndex()
        if pi == 0:   phases = ["all"]
        elif pi == 1: phases = ["P"]
        elif pi == 2: phases = ["S"]
        elif pi == 3: phases = ["P", "S"]
        else:         phases = FilterConfig.parse_phase_string(self._phase_custom.text())

        # Spatial — bbox: only active when lat/lon span is non-zero
        la0 = self._bbox_lat_min.value()
        la1 = self._bbox_lat_max.value()
        lo0 = self._bbox_lon_min.value()
        lo1 = self._bbox_lon_max.value()
        bbox = (la0, la1, lo0, lo1) if (la1 > la0 or lo1 > lo0) else None

        radius_km  = self._radius_km.value() if self._radius_km.value() > 0.0 else None
        center_lat = self._center_lat.value() if radius_km else None
        center_lon = self._center_lon.value() if radius_km else None

        # Temporal
        start_time = self._start_time.text().strip() or None
        end_time   = self._end_time.text().strip() or None

        # Quality
        max_gap     = self._max_gap.value() if self._max_gap.value() > 0.0 else None
        min_phases  = self._min_phases.value() if self._min_phases.value() > 0 else None
        max_rms     = self._max_rms.value() if self._max_rms.value() > 0.0 else None
        max_dep_unc = self._max_dep_unc.value() if self._max_dep_unc.value() > 0.0 else None

        return FilterConfig(
            arrivals=arrivals,
            min_magnitude=min_mag,
            max_magnitude=max_mag,
            max_distance=max_dist,
            phases=phases,
            bbox=bbox,
            center_lat=center_lat,
            center_lon=center_lon,
            radius_km=radius_km,
            start_time=start_time,
            end_time=end_time,
            max_azimuthal_gap=max_gap,
            min_used_phases=min_phases,
            max_rms=max_rms,
            max_depth_uncertainty=max_dep_unc,
        )

    def set_config(self, cfg: FilterConfig):
        # Basic
        self._arrivals_combo.setCurrentIndex(
            {"all": 0, "used": 1, "unused": 2}.get(cfg.arrivals, 0)
        )
        self._min_mag.setValue(cfg.min_magnitude or 0.0)
        self._max_mag.setValue(cfg.max_magnitude or 0.0)
        self._max_dist.setValue(cfg.max_distance or 0.0)

        if not cfg.phases or cfg.phases == ["all"]:
            self._phase_combo.setCurrentIndex(0)
        elif cfg.phases == ["P"]:
            self._phase_combo.setCurrentIndex(1)
        elif cfg.phases == ["S"]:
            self._phase_combo.setCurrentIndex(2)
        elif set(cfg.phases) == {"P", "S"}:
            self._phase_combo.setCurrentIndex(3)
        else:
            self._phase_combo.setCurrentIndex(4)
            self._phase_custom.setText(",".join(cfg.phases))
            self._phase_custom.setVisible(True)

        # Spatial
        if cfg.bbox:
            la0, la1, lo0, lo1 = cfg.bbox
            self._bbox_lat_min.setValue(la0)
            self._bbox_lat_max.setValue(la1)
            self._bbox_lon_min.setValue(lo0)
            self._bbox_lon_max.setValue(lo1)
        if cfg.center_lat is not None:
            self._center_lat.setValue(cfg.center_lat)
        if cfg.center_lon is not None:
            self._center_lon.setValue(cfg.center_lon)
        self._radius_km.setValue(cfg.radius_km or 0.0)

        # Temporal
        self._start_time.setText(cfg.start_time or "")
        self._end_time.setText(cfg.end_time or "")

        # Quality
        self._max_gap.setValue(cfg.max_azimuthal_gap or 0.0)
        self._min_phases.setValue(cfg.min_used_phases or 0)
        self._max_rms.setValue(cfg.max_rms or 0.0)
        self._max_dep_unc.setValue(cfg.max_depth_uncertainty or 0.0)
