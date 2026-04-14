"""
SeisComP XML parser — Python port of the web tool's extraction logic.
Handles schema versions 0.5–0.14 and forward-compatible unknown versions
via namespace-aware ElementTree queries.
"""
from __future__ import annotations

import math
import re as _re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .filters import FilterConfig
from .schema import detect_namespace

# ──────────────────────────────────────────────────────────────────────────────
# Phase classification helpers
# ──────────────────────────────────────────────────────────────────────────────

_P_PHASES = {"P", "PG", "PN", "PP", "PKP", "PKIKP", "PKIKKIKP", "PKJKP", "PKKS"}
_S_PHASES = {"S", "SG", "SN", "SS", "SKS", "SKIKS", "SKIKKIKS", "SKJKS", "SKKS"}


def is_p_phase(phase: str) -> bool:
    p = phase.upper()
    return p in _P_PHASES or p.startswith("P")


def is_s_phase(phase: str) -> bool:
    s = phase.upper()
    return s in _S_PHASES or s.startswith("S")


# ──────────────────────────────────────────────────────────────────────────────
# Tiny type-coercion helpers
# ──────────────────────────────────────────────────────────────────────────────

def _float(text: Optional[str]) -> Optional[float]:
    try:
        return float(text) if text is not None else None
    except (ValueError, TypeError):
        return None


def _int(text: Optional[str]) -> Optional[int]:
    try:
        return int(text) if text is not None else None
    except (ValueError, TypeError):
        return None


def _bool(text: Optional[str]) -> Optional[bool]:
    if text is None:
        return None
    return text.strip().lower() == "true"


def _parse_iso(time_str: str) -> Optional[float]:
    """ISO-8601 string → Unix timestamp (float), or None on failure."""
    if not time_str:
        return None
    try:
        s = time_str.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, AttributeError):
        return None


def _ts_to_parts(ts: float) -> tuple[str, str]:
    """Unix timestamp → (YYYY-MM-DD, HH:MM:SS.mmm)"""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S.%f")[:-3]


# ──────────────────────────────────────────────────────────────────────────────
# Spatial helper
# ──────────────────────────────────────────────────────────────────────────────

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km (Haversine formula)."""
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    return 2.0 * R * math.asin(math.sqrt(a))


# ──────────────────────────────────────────────────────────────────────────────
# Location quality score (0–100)
# ──────────────────────────────────────────────────────────────────────────────

def _compute_secondary_azimuthal_gap(
    origin_el: ET.Element,
    ns: "_NS",
    id_index: dict | None = None,
) -> Optional[float]:
    """
    Compute the secondary azimuthal gap from used arrival azimuths.
    Same algorithm as scautoloc/stdloc: max(azi[i+2] - azi[i]) over sorted azimuths.

    One azimuth per station (NET.STA) is used so that events with both P
    and S used from the same station are not double-counted.
    Returns None if fewer than 2 unique used stations with azimuth data.
    """
    seen_sta: set[str] = set()
    azimuths: list[float] = []
    for arr_el in ns.iter(origin_el, "arrival"):
        if _bool(ns.text(arr_el, "timeUsed")) is not True:
            continue
        az = _float(ns.text(arr_el, "azimuth"))
        if az is None:
            continue
        # Derive a per-station key for deduplication
        pick_id = ns.text(arr_el, "pickID") or ""
        sta_key = ""
        if id_index and pick_id:
            pick_el = id_index.get(pick_id)
            if pick_el is not None:
                wf = pick_el.find(ns.q("waveformID"))
                if wf is not None:
                    sta_key = (
                        f"{wf.get('networkCode','')}.{wf.get('stationCode','')}"
                    )
        if not sta_key:
            nslc = _parse_pick_id_nslc(pick_id)
            sta_key = f"{nslc[0]}.{nslc[1]}" if nslc else f"az:{az:.4f}"
        if sta_key in seen_sta:
            continue
        seen_sta.add(sta_key)
        azimuths.append(az)

    if len(azimuths) < 2:
        return None

    azimuths.sort()
    n = len(azimuths)
    azimuths.append(azimuths[0] + 360.0)
    azimuths.append(azimuths[1] + 360.0)

    secondary = 0.0
    for i in range(n):
        gap = azimuths[i + 2] - azimuths[i]
        if gap > secondary:
            secondary = gap

    return round(secondary, 2)


def _compute_quality_score(info: dict) -> Optional[float]:
    """
    Composite quality score 0–100:
      30 pts  azimuthal gap  (0° → 30, 360° → 0)
      25 pts  RMS            (0 s → 25, ≥2 s → 0)
      25 pts  used phases    (0 → 0, ≥10 → 25)
      20 pts  minimum dist   (0° → 20, ≥10° → 0)
    """
    gap      = info.get("origin_quality_azimuthal_gap")
    rms      = info.get("origin_quality_standard_error")
    nph      = info.get("origin_quality_used_phase_count")
    min_dist = info.get("origin_quality_minimum_distance")

    if gap is None and rms is None and nph is None and min_dist is None:
        return None

    score = 0.0
    if gap is not None:
        score += 30.0 * max(0.0, 1.0 - float(gap) / 360.0)
    if rms is not None:
        score += 25.0 * max(0.0, 1.0 - float(rms) / 2.0)
    if nph is not None:
        score += min(25.0, float(nph) * 2.5)
    if min_dist is not None:
        score += 20.0 * max(0.0, 1.0 - float(min_dist) / 10.0)

    return round(score, 1)


# ──────────────────────────────────────────────────────────────────────────────
# Namespace-aware element helper
# ──────────────────────────────────────────────────────────────────────────────

class _NS:
    """Wraps namespace URI for concise ElementTree queries."""

    __slots__ = ("_pfx",)

    def __init__(self, ns_uri: str) -> None:
        self._pfx = f"{{{ns_uri}}}" if ns_uri else ""

    def q(self, name: str) -> str:
        return f"{self._pfx}{name}"

    def find(self, el: ET.Element, path: str) -> Optional[ET.Element]:
        cur = el
        for part in path.split("/"):
            if cur is None:
                return None
            cur = cur.find(self.q(part))
        return cur

    def text(self, el: ET.Element, path: str) -> Optional[str]:
        found = self.find(el, path)
        return found.text if found is not None else None

    def iter(self, el: ET.Element, name: str):
        return el.iter(self.q(name))


# ──────────────────────────────────────────────────────────────────────────────
# Main parser class
# ──────────────────────────────────────────────────────────────────────────────

class SeisCompParser:
    """
    Parses SeisComP XML files and returns extraction results.

    Each call to parse_file / parse_string returns a list of dicts:
        {
          "eventId":      str,
          "fileName":     str,
          "stationCount": int,
          "schemaVersion":str,
          "records":      list[dict],   # one dict per arrival
        }
    """

    def parse_file(
        self,
        path: str | Path,
        filters: FilterConfig,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> list[dict]:
        path = Path(path)
        try:
            tree = ET.parse(path)
        except ET.ParseError as exc:
            raise ValueError(f"XML parse error in '{path.name}': {exc}") from exc
        return self._parse_root(tree.getroot(), path.name, filters, progress_callback)

    def parse_string(
        self,
        content: str,
        filename: str,
        filters: FilterConfig,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> list[dict]:
        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            raise ValueError(f"XML parse error in '{filename}': {exc}") from exc
        return self._parse_root(root, filename, filters, progress_callback)

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _parse_root(
        self,
        root: ET.Element,
        filename: str,
        filters: FilterConfig,
        progress_callback: Optional[Callable],
    ) -> list[dict]:
        ns_uri, schema_version = detect_namespace(root)
        ns = _NS(ns_uri)

        id_index: Dict[str, ET.Element] = {
            elem.get("publicID"): elem
            for elem in root.iter()
            if elem.get("publicID")
        }

        event_elements = list(ns.iter(root, "event"))
        results: list[dict] = []

        for i, ev_el in enumerate(event_elements):
            if progress_callback:
                progress_callback(i, len(event_elements),
                                  f"Parsing event {i+1}/{len(event_elements)}")
            result = self._extract_event(
                ev_el, filename, filters, ns, id_index, schema_version
            )
            if result and result["records"]:
                results.append(result)

        return results

    # ------------------------------------------------------------------ #

    def _extract_event(
        self,
        ev_el: ET.Element,
        filename: str,
        filters: FilterConfig,
        ns: _NS,
        id_index: Dict[str, ET.Element],
        schema_version: str,
    ) -> Optional[dict]:
        event_id = ev_el.get("publicID", "Unknown")

        event_type            = ns.text(ev_el, "type") or ""
        event_type_certainty  = ns.text(ev_el, "typeCertainty") or ""
        preferred_origin_id   = ns.text(ev_el, "preferredOriginID")
        preferred_mag_id      = ns.text(ev_el, "preferredMagnitudeID")

        if not preferred_origin_id:
            return None

        event_comments = "; ".join(
            ns.text(c, "text") or ""
            for c in ns.iter(ev_el, "comment")
            if ns.text(c, "text")
        ) or None

        event_info = self._extract_event_info(
            preferred_origin_id, preferred_mag_id,
            event_id, filename,
            event_type, event_type_certainty, event_comments,
            ns, id_index,
        )

        # ── Event-level filters ──────────────────────────────────────────
        mag_val  = event_info.get("event_magnitude_value")
        ev_lat   = event_info.get("event_latitude")
        ev_lon   = event_info.get("event_longitude")
        ev_ts    = event_info.get("event_timestamp")
        gap      = event_info.get("origin_quality_azimuthal_gap")
        nph      = event_info.get("origin_quality_used_phase_count")
        rms      = event_info.get("origin_quality_standard_error")
        dep_unc  = event_info.get("event_depth_uncertainty")

        if filters.min_magnitude is not None and mag_val is not None:
            if mag_val < filters.min_magnitude:
                return None
        if filters.max_magnitude is not None and mag_val is not None:
            if mag_val > filters.max_magnitude:
                return None

        if (filters.bbox is not None
                and ev_lat is not None and ev_lon is not None):
            la0, la1, lo0, lo1 = filters.bbox
            if not (la0 <= ev_lat <= la1 and lo0 <= ev_lon <= lo1):
                return None

        if (filters.radius_km is not None
                and filters.center_lat is not None
                and filters.center_lon is not None
                and ev_lat is not None and ev_lon is not None):
            if _haversine(filters.center_lat, filters.center_lon,
                          ev_lat, ev_lon) > filters.radius_km:
                return None

        if filters.start_time is not None and ev_ts is not None:
            start_ts = _parse_iso(filters.start_time)
            if start_ts is not None and ev_ts < start_ts:
                return None
        if filters.end_time is not None and ev_ts is not None:
            end_ts = _parse_iso(filters.end_time)
            if end_ts is not None and ev_ts > end_ts:
                return None

        if filters.max_azimuthal_gap is not None and gap is not None:
            if gap > filters.max_azimuthal_gap:
                return None
        if filters.min_used_phases is not None and nph is not None:
            if nph < filters.min_used_phases:
                return None
        if filters.max_rms is not None and rms is not None:
            if rms > filters.max_rms:
                return None
        if filters.max_depth_uncertainty is not None and dep_unc is not None:
            if dep_unc > filters.max_depth_uncertainty:
                return None

        records = self._extract_stations_for_origin(
            preferred_origin_id, event_info, filters, ns, id_index
        )

        return {
            "eventId":       event_id,
            "fileName":      filename,
            "stationCount":  len(records),
            "schemaVersion": schema_version,
            "records":       records,
        }

    # ------------------------------------------------------------------ #

    def _extract_event_info(
        self,
        origin_id: str,
        magnitude_id: Optional[str],
        event_id: str,
        filename: str,
        event_type: str,
        event_type_certainty: str,
        event_comments: Optional[str],
        ns: _NS,
        id_index: Dict[str, ET.Element],
    ) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "eventID":                event_id,
            "event_type":             event_type,
            "event_type_certainty":   event_type_certainty,
            "file_name":              filename,
            "processing_timestamp":   datetime.now(tz=timezone.utc).isoformat(),
            "preferred_origin_id":    origin_id,
            "preferred_magnitude_id": magnitude_id,
            "event_comments":         event_comments,
        }

        origin_el = id_index.get(origin_id)
        if origin_el is not None:
            time_str = ns.text(origin_el, "time/value")
            if time_str:
                ts = _parse_iso(time_str)
                if ts is not None:
                    info["event_timestamp"] = ts
                    info["event_date"], info["event_time"] = _ts_to_parts(ts)

            info["event_latitude"]              = _float(ns.text(origin_el, "latitude/value"))
            info["event_longitude"]             = _float(ns.text(origin_el, "longitude/value"))
            info["event_depth"]                 = _float(ns.text(origin_el, "depth/value"))
            info["event_latitude_uncertainty"]  = _float(ns.text(origin_el, "latitude/uncertainty"))
            info["event_longitude_uncertainty"] = _float(ns.text(origin_el, "longitude/uncertainty"))
            info["event_depth_uncertainty"]     = _float(ns.text(origin_el, "depth/uncertainty"))

            # Depth constraint type
            info["depth_constraint"] = ns.text(origin_el, "depthType")

            q_el = ns.find(origin_el, "quality")
            if q_el is not None:
                for xml_key, dict_key in _QUALITY_FIELDS:
                    raw = ns.text(q_el, xml_key)
                    if raw is not None:
                        info[dict_key] = _float(raw) if _float(raw) is not None else raw

            # Fallback: compute secondary azimuthal gap from arrival azimuths
            # when not stored in the XML (e.g. scautoloc origins)
            if info.get("origin_quality_secondary_azimuthal_gap") is None:
                sec_gap = _compute_secondary_azimuthal_gap(origin_el, ns, id_index)
                if sec_gap is not None:
                    info["origin_quality_secondary_azimuthal_gap"] = sec_gap

            # Location quality score
            info["location_quality_score"] = _compute_quality_score(info)

            ci_el = ns.find(origin_el, "creationInfo")
            if ci_el is not None:
                info["event_author"]        = ns.text(ci_el, "author")
                info["event_agency"]        = ns.text(ci_el, "agencyID")
                info["event_creation_time"] = ns.text(ci_el, "creationTime")

            info["event_evaluation_mode"]   = ns.text(origin_el, "evaluationMode")
            info["event_evaluation_status"] = ns.text(origin_el, "evaluationStatus")

            info["origin_comments"] = "; ".join(
                ns.text(c, "text") or ""
                for c in ns.iter(origin_el, "comment")
                if ns.text(c, "text")
            ) or None

        # Magnitude
        if magnitude_id:
            mag_el = id_index.get(magnitude_id)
            if mag_el is not None:
                info["event_magnitude_type"]          = ns.text(mag_el, "type")
                info["event_magnitude_value"]         = _float(ns.text(mag_el, "magnitude/value"))
                info["event_magnitude_uncertainty"]   = _float(ns.text(mag_el, "magnitude/uncertainty"))
                info["event_magnitude_station_count"] = _int(ns.text(mag_el, "stationCount"))
                info["event_magnitude_method"]        = ns.text(mag_el, "methodID")
                info["event_magnitude_azimuthal_gap"] = _float(ns.text(mag_el, "azimuthalGap"))
                info["magnitude_evaluation_mode"]     = ns.text(mag_el, "evaluationMode")
                info["magnitude_evaluation_status"]   = ns.text(mag_el, "evaluationStatus")

                mag_ci = ns.find(mag_el, "creationInfo")
                if mag_ci is not None:
                    info["event_magnitude_author"] = ns.text(mag_ci, "author")

                info["magnitude_comments"] = "; ".join(
                    ns.text(c, "text") or ""
                    for c in ns.iter(mag_el, "comment")
                    if ns.text(c, "text")
                ) or None

                # Station magnitude contribution lookup (for residual/used fields)
                sm_contribs: dict[str, tuple] = {}
                for contrib in ns.iter(mag_el, "stationMagnitudeContribution"):
                    sm_id = ns.text(contrib, "stationMagnitudeID")
                    res   = _float(ns.text(contrib, "residual"))
                    wt    = _float(ns.text(contrib, "weight"))
                    used  = (wt is None or wt > 0)
                    if sm_id:
                        sm_contribs[sm_id] = (res, used)
                info["_sm_contributions"] = sm_contribs

        return info

    # ------------------------------------------------------------------ #

    def _extract_stations_for_origin(
        self,
        origin_id: str,
        event_info: Dict[str, Any],
        filters: FilterConfig,
        ns: _NS,
        id_index: Dict[str, ET.Element],
    ) -> List[Dict[str, Any]]:
        origin_el = id_index.get(origin_id)
        if origin_el is None:
            return []

        sm_contribs: dict[str, tuple] = event_info.get("_sm_contributions") or {}
        origin_ts = event_info.get("event_timestamp")

        station_buckets: Dict[str, List[Dict]] = {}

        for arr_el in ns.iter(origin_el, "arrival"):
            rec = self._extract_arrival(arr_el, event_info, filters, ns, id_index)
            if rec is None:
                continue
            key = f"{rec.get('station_network','')}.{rec.get('station_code','')}"
            station_buckets.setdefault(key, []).append(rec)

        records: List[Dict] = []

        for picks in station_buckets.values():
            picks.sort(key=lambda r: (
                0 if is_p_phase(r.get("phase", "")) else 1,
                r.get("_pick_ts", 0) or 0,
            ))

            p_ts = s_ts = None
            p_ts_used = s_ts_used = None
            p_used = s_used = None

            for rec in picks:
                phase   = (rec.get("phase") or "").upper()
                ts      = rec.get("_pick_ts")
                is_used = rec.get("arrival_time_used") is True

                if is_p_phase(phase) and p_ts is None:
                    p_ts  = ts
                    p_used = is_used
                    if ts is not None and origin_ts is not None:
                        rec["travel_time_p"] = round(ts - origin_ts, 3)
                    if is_used:
                        p_ts_used = ts

                elif is_s_phase(phase) and s_ts is None:
                    s_ts  = ts
                    s_used = is_used
                    if ts is not None and origin_ts is not None:
                        rec["travel_time_s"] = round(ts - origin_ts, 3)
                    if is_used:
                        s_ts_used = ts

            sp = (round(s_ts - p_ts, 3)
                  if p_ts and s_ts and s_ts > p_ts else None)
            sp_used_only = (round(s_ts_used - p_ts_used, 3)
                            if p_ts_used and s_ts_used and s_ts_used > p_ts_used else None)
            sp_quality = bool(p_used is True and s_used is True)

            # Collect travel times and distance for velocity estimates
            p_tp   = next((r["travel_time_p"] for r in picks if r.get("travel_time_p") is not None), None)
            s_ts_v = next((r["travel_time_s"] for r in picks if r.get("travel_time_s") is not None), None)
            dist_km = next((r["distance_km"] for r in picks if r.get("distance_km") is not None), None)

            vp_est = round(dist_km / p_tp, 3) if (dist_km and p_tp and p_tp > 0) else None
            vs_est = round(dist_km / s_ts_v, 3) if (dist_km and s_ts_v and s_ts_v > 0) else None
            vp_vs  = round(s_ts_v / p_tp, 3) if (p_tp and s_ts_v and p_tp > 0) else None

            for rec in picks:
                rec["sp_time"]           = sp
                rec["sp_time_quality"]   = sp_quality
                rec["sp_time_used_only"] = sp_used_only
                rec["p_arrival_used"]    = p_used
                rec["s_arrival_used"]    = s_used
                rec["vp_estimate"]       = vp_est
                rec["vs_estimate"]       = vs_est
                rec["vp_vs_ratio"]       = vp_vs

                # Per-phase predicted travel times
                phase = (rec.get("phase") or "").upper()
                residual = rec.get("arrival_residual")

                if is_p_phase(phase) and rec.get("travel_time_p") is not None:
                    tp = rec["travel_time_p"]
                    rec["travel_time_residual_p"] = residual
                    if residual is not None:
                        pred = round(tp - residual, 3)
                        rec["predicted_travel_time_p"] = pred
                        if origin_ts is not None:
                            _, rec["theoretical_arrival_time"] = _ts_to_parts(origin_ts + pred)

                elif is_s_phase(phase) and rec.get("travel_time_s") is not None:
                    ts_v = rec["travel_time_s"]
                    rec["travel_time_residual_s"] = residual
                    if residual is not None:
                        pred = round(ts_v - residual, 3)
                        rec["predicted_travel_time_s"] = pred

                rec["pick_timestamp"] = rec.pop("_pick_ts", None)
                self._add_station_magnitude(origin_el, rec, ns, sm_contribs)
                records.append(rec)

        # Remove private key from all records
        for rec in records:
            rec.pop("_sm_contributions", None)

        return records

    # ------------------------------------------------------------------ #

    def _extract_arrival(
        self,
        arr_el: ET.Element,
        event_info: Dict[str, Any],
        filters: FilterConfig,
        ns: _NS,
        id_index: Dict[str, ET.Element],
    ) -> Optional[Dict[str, Any]]:
        pick_id = ns.text(arr_el, "pickID")
        if not pick_id:
            return None

        pick_el = id_index.get(pick_id)

        rec = dict(event_info)
        rec["pick_id"] = pick_id

        # ── Pick time ──────────────────────────────────────────────
        if pick_el is not None:
            time_str = ns.text(pick_el, "time/value")
        else:
            time_str = None

        if time_str:
            ts = _parse_iso(time_str)
        else:
            ts = _parse_pick_id_time(pick_id)
            time_str = None

        if ts is None:
            return None

        rec["_pick_ts"] = ts
        _, rec["pick_time"] = _ts_to_parts(ts)
        if time_str:
            rec["observed_arrival_time"] = time_str.strip()

        # ── Phase + phase filter ────────────────────────────────────
        phase = ns.text(arr_el, "phase") or "Unknown"
        rec["phase"] = phase
        if filters.phases and filters.phases != ["all"]:
            if not _phase_matches(phase, filters.phases):
                return None

        # ── Pick metadata ───────────────────────────────────────────
        if pick_el is not None:
            rec["pick_quality"]           = ns.text(pick_el, "evaluationMode")
            rec["pick_evaluation_mode"]   = ns.text(pick_el, "evaluationMode")
            rec["pick_evaluation_status"] = ns.text(pick_el, "evaluationStatus")
            rec["pick_uncertainty"]       = _float(ns.text(pick_el, "time/uncertainty"))
            rec["pick_polarity"]          = ns.text(pick_el, "polarity")
            rec["pick_onset"]             = ns.text(pick_el, "onset")
            rec["pick_filter_id"]         = ns.text(pick_el, "filterID")

            pick_ci = ns.find(pick_el, "creationInfo")
            if pick_ci is not None:
                rec["pick_author"]        = ns.text(pick_ci, "author")
                rec["pick_agency"]        = ns.text(pick_ci, "agencyID")
                rec["pick_creation_time"] = ns.text(pick_ci, "creationTime")
                rec["pick_method"]        = ns.text(pick_ci, "methodID")

            wf_el = ns.find(pick_el, "waveformID")
            if wf_el is not None:
                rec["station_network"]  = wf_el.get("networkCode", "")
                rec["station_code"]     = wf_el.get("stationCode", "")
                rec["station_location"] = wf_el.get("locationCode", "")
                rec["station_channel"]  = wf_el.get("channelCode", "")
        else:
            nslc = _parse_pick_id_nslc(pick_id)
            if nslc:
                rec["station_network"]  = nslc[0]
                rec["station_code"]     = nslc[1]
                rec["station_location"] = nslc[2]
                rec["station_channel"]  = nslc[3]

        # ── Arrival measurements ────────────────────────────────────
        rec["arrival_distance"] = _float(ns.text(arr_el, "distance"))
        rec["arrival_azimuth"]  = _float(ns.text(arr_el, "azimuth"))
        rec["arrival_residual"] = _float(ns.text(arr_el, "timeResidual"))
        rec["arrival_weight"]   = _float(ns.text(arr_el, "weight"))
        rec["arrival_time_used"] = _bool(ns.text(arr_el, "timeUsed"))

        # Distance in km (1° ≈ 111.195 km)
        dist_deg = rec["arrival_distance"]
        rec["distance_km"] = round(dist_deg * 111.195, 2) if dist_deg is not None else None

        # Distance filter
        if filters.max_distance is not None and dist_deg is not None:
            if dist_deg > filters.max_distance:
                return None

        # Arrival usage filter
        time_used = rec["arrival_time_used"]
        if filters.arrivals == "used" and time_used is False:
            return None
        if filters.arrivals == "unused" and time_used is True:
            return None

        rec["arrival_horizontal_slowness_residual"] = _float(ns.text(arr_el, "horizontalSlownessResidual"))
        rec["arrival_backazimuth_residual"]          = _float(ns.text(arr_el, "backazimuthResidual"))
        rec["arrival_horizontal_slowness_weight"]    = _float(ns.text(arr_el, "horizontalSlownessWeight"))
        rec["arrival_backazimuth_weight"]             = _float(ns.text(arr_el, "backazimuthWeight"))
        rec["arrival_horizontal_slowness_used"]      = _bool(ns.text(arr_el, "horizontalSlownessUsed"))
        rec["arrival_backazimuth_used"]              = _bool(ns.text(arr_el, "backazimuthUsed"))
        rec["arrival_take_off_angle"]                = _float(ns.text(arr_el, "takeOffAngle"))
        rec["arrival_take_off_angle_used"]           = _bool(ns.text(arr_el, "takeOffAngleUsed"))

        rec["arrival_comments"] = "; ".join(
            ns.text(c, "text") or "" for c in ns.iter(arr_el, "comment")
            if ns.text(c, "text")
        ) or None
        rec["pick_comments"] = ("; ".join(
            ns.text(c, "text") or "" for c in ns.iter(pick_el, "comment")
            if ns.text(c, "text")
        ) or None) if pick_el is not None else None

        for f in ("station_latitude", "station_longitude", "station_elevation",
                  "station_description", "station_site_name", "station_country",
                  "station_restricted_status", "station_start_date", "station_end_date"):
            rec.setdefault(f, None)

        return rec

    # ------------------------------------------------------------------ #

    def _add_station_magnitude(
        self,
        origin_el: ET.Element,
        rec: Dict[str, Any],
        ns: _NS,
        sm_contributions: dict | None = None,
    ) -> None:
        for k in ("station_magnitude_type", "station_magnitude_value",
                  "station_magnitude_uncertainty", "station_magnitude_residual",
                  "station_magnitude_used", "station_magnitude_method",
                  "station_magnitude_creation_time", "station_magnitude_author",
                  "station_magnitude_agency"):
            rec[k] = None

        net = rec.get("station_network", "")
        sta = rec.get("station_code", "")

        for sm_el in ns.iter(origin_el, "stationMagnitude"):
            wf_el = ns.find(sm_el, "waveformID")
            if (wf_el is not None
                    and wf_el.get("networkCode") == net
                    and wf_el.get("stationCode") == sta):
                rec["station_magnitude_type"]        = ns.text(sm_el, "type")
                rec["station_magnitude_value"]       = _float(ns.text(sm_el, "magnitude/value"))
                rec["station_magnitude_uncertainty"] = _float(ns.text(sm_el, "magnitude/uncertainty"))
                rec["station_magnitude_method"]      = ns.text(sm_el, "methodID")

                ci = ns.find(sm_el, "creationInfo")
                if ci is not None:
                    rec["station_magnitude_author"]        = ns.text(ci, "author")
                    rec["station_magnitude_agency"]        = ns.text(ci, "agencyID")
                    rec["station_magnitude_creation_time"] = ns.text(ci, "creationTime")

                # Residual and used flag from network mag contributions
                if sm_contributions:
                    sm_pub_id = sm_el.get("publicID", "")
                    if sm_pub_id in sm_contributions:
                        res, used = sm_contributions[sm_pub_id]
                        rec["station_magnitude_residual"] = res
                        rec["station_magnitude_used"]     = used
                break


# ──────────────────────────────────────────────────────────────────────────────
# pickID string parsers (fallback for arrivals-only files)
# ──────────────────────────────────────────────────────────────────────────────

# SeisComP standard pickID: YYYYMMDD.HHMMSS.CC-METHOD-NET.STA.LOC.CHA
# e.g. "20210424.004314.60-AIC-G.TAM.00.BHZ"
_PICK_ID_RE = _re.compile(
    r"^(\d{4})(\d{2})(\d{2})\."
    r"(\d{2})(\d{2})(\d{2})\.(\d+)"
    r"-[^-]+-"
    r"([^.]+)\.([^.]+)\.([^.]*)\.(\w+)$"
)


def _parse_pick_id_time(pick_id: str) -> Optional[float]:
    m = _PICK_ID_RE.match(pick_id)
    if not m:
        return None
    yr, mo, dy, hh, mm, ss, frac = m.group(1, 2, 3, 4, 5, 6, 7)
    frac_str = frac[:6].ljust(6, "0")
    return _parse_iso(f"{yr}-{mo}-{dy}T{hh}:{mm}:{ss}.{frac_str}+00:00")


def _parse_pick_id_nslc(pick_id: str) -> Optional[tuple[str, str, str, str]]:
    m = _PICK_ID_RE.match(pick_id)
    if m:
        return m.group(8), m.group(9), m.group(10), m.group(11)
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Module-level helpers
# ──────────────────────────────────────────────────────────────────────────────

def _phase_matches(phase: str, allowed: list[str]) -> bool:
    p = phase.upper()
    for a in allowed:
        a = a.strip().upper()
        if a == "P" and is_p_phase(p):
            return True
        if a == "S" and is_s_phase(p):
            return True
        if p.startswith(a):
            return True
    return False


_QUALITY_FIELDS: list[tuple[str, str]] = [
    ("associatedPhaseCount",   "origin_quality_associated_phase_count"),
    ("usedPhaseCount",         "origin_quality_used_phase_count"),
    ("associatedStationCount", "origin_quality_associated_station_count"),
    ("usedStationCount",       "origin_quality_used_station_count"),
    ("depthPhaseCount",        "origin_quality_depth_phase_count"),
    ("standardError",          "origin_quality_standard_error"),
    ("azimuthalGap",           "origin_quality_azimuthal_gap"),
    ("secondaryAzimuthalGap",  "origin_quality_secondary_azimuthal_gap"),
    ("groundTruthLevel",       "origin_quality_ground_truth_level"),
    ("maximumDistance",        "origin_quality_maximum_distance"),
    ("minimumDistance",        "origin_quality_minimum_distance"),
    ("medianDistance",         "origin_quality_median_distance"),
]
