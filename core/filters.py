"""
Filter configuration dataclass for SeisComP data extraction.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FilterConfig:
    """All filter settings for one extraction run."""

    # Arrival usage: 'all' | 'used' | 'unused'
    arrivals: str = "all"

    # Magnitude thresholds
    min_magnitude: Optional[float] = None
    max_magnitude: Optional[float] = None

    # Distance cutoff in degrees
    max_distance: Optional[float] = None

    # Phase list: ['all'] means no filtering.
    phases: list[str] = field(default_factory=lambda: ["all"])

    # Spatial: bounding box (lat_min, lat_max, lon_min, lon_max)
    bbox: Optional[tuple] = None   # 4-tuple of floats

    # Spatial: radius filter
    center_lat: Optional[float] = None
    center_lon: Optional[float] = None
    radius_km: Optional[float] = None

    # Temporal: ISO 8601 strings (e.g. "2021-01-01T00:00:00")
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    # Origin quality thresholds
    max_azimuthal_gap: Optional[float] = None    # degrees
    min_used_phases: Optional[int] = None
    max_rms: Optional[float] = None              # seconds
    max_depth_uncertainty: Optional[float] = None  # km

    # ------------------------------------------------------------------ #
    # Serialisation helpers                                                #
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict:
        return {
            "arrivals":              self.arrivals,
            "min_magnitude":         self.min_magnitude,
            "max_magnitude":         self.max_magnitude,
            "max_distance":          self.max_distance,
            "phases":                self.phases,
            "bbox":                  list(self.bbox) if self.bbox else None,
            "center_lat":            self.center_lat,
            "center_lon":            self.center_lon,
            "radius_km":             self.radius_km,
            "start_time":            self.start_time,
            "end_time":              self.end_time,
            "max_azimuthal_gap":     self.max_azimuthal_gap,
            "min_used_phases":       self.min_used_phases,
            "max_rms":               self.max_rms,
            "max_depth_uncertainty": self.max_depth_uncertainty,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FilterConfig":
        bbox_raw = d.get("bbox")
        bbox = tuple(bbox_raw) if bbox_raw and len(bbox_raw) == 4 else None
        return cls(
            arrivals=d.get("arrivals", "all"),
            min_magnitude=d.get("min_magnitude"),
            max_magnitude=d.get("max_magnitude"),
            max_distance=d.get("max_distance"),
            phases=d.get("phases", ["all"]),
            bbox=bbox,
            center_lat=d.get("center_lat"),
            center_lon=d.get("center_lon"),
            radius_km=d.get("radius_km"),
            start_time=d.get("start_time"),
            end_time=d.get("end_time"),
            max_azimuthal_gap=d.get("max_azimuthal_gap"),
            min_used_phases=d.get("min_used_phases"),
            max_rms=d.get("max_rms"),
            max_depth_uncertainty=d.get("max_depth_uncertainty"),
        )

    # ------------------------------------------------------------------ #
    # Convenience                                                          #
    # ------------------------------------------------------------------ #

    @property
    def phase_filter_display(self) -> str:
        if not self.phases or self.phases == ["all"]:
            return "All phases"
        return ", ".join(self.phases)

    @staticmethod
    def parse_phase_string(s: str) -> list[str]:
        """'P,S' → ['P','S'],  'all' → ['all']"""
        s = s.strip()
        if not s or s.lower() == "all":
            return ["all"]
        return [p.strip().upper() for p in s.split(",") if p.strip()]
