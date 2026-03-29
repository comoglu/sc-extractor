"""
Catalog statistics for SeisComP extraction results.

Provides:
  - Gutenberg-Richter b-value (maximum likelihood, Aki 1965)
  - Magnitude of completeness Mc (maximum curvature method)
  - Per-station residual statistics
  - Network summary report
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────────────────────────────────────
# Magnitude of completeness — maximum curvature
# ──────────────────────────────────────────────────────────────────────────────

def compute_mc(magnitudes: list[float], bin_width: float = 0.1) -> float:
    """Return Mc as the magnitude bin with the highest frequency."""
    if not magnitudes:
        return 0.0
    bins: dict[float, int] = {}
    for m in magnitudes:
        b = round(round(m / bin_width) * bin_width, 4)
        bins[b] = bins.get(b, 0) + 1
    return round(max(bins, key=lambda b: bins[b]), 2)


# ──────────────────────────────────────────────────────────────────────────────
# Gutenberg-Richter b-value
# ──────────────────────────────────────────────────────────────────────────────

def compute_b_value(
    magnitudes: list[float],
    mc: Optional[float] = None,
    bin_width: float = 0.1,
) -> dict:
    """
    Maximum-likelihood b-value estimator (Aki 1965).
    b = log10(e) / (mean_M - (Mc - dM/2))

    Returns dict: b_value, b_value_uncertainty, a_value, mc, n_events,
                  n_events_total, mean_magnitude, r_squared
    """
    if not magnitudes:
        return {"b_value": None, "n_events": 0, "n_events_total": 0}

    if mc is None:
        mc = compute_mc(magnitudes, bin_width)

    above = [m for m in magnitudes if m >= mc]
    n = len(above)

    if n < 2:
        return {
            "b_value": None, "a_value": None, "mc": mc,
            "n_events": n, "n_events_total": len(magnitudes),
            "mean_magnitude": above[0] if above else None,
        }

    mean_m = sum(above) / n
    denom = mean_m - (mc - bin_width / 2.0)
    if denom <= 0:
        return {"b_value": None, "a_value": None, "mc": mc,
                "n_events": n, "n_events_total": len(magnitudes)}

    b = math.log10(math.e) / denom
    # Shi & Bolt (1982) uncertainty
    b_unc = 2.3 * b ** 2 * math.sqrt(
        sum((m - mean_m) ** 2 for m in above) / (n * (n - 1))
    )
    a = math.log10(n) + b * mc

    # R² between observed and GR-predicted cumulative counts
    bin_vals = sorted(set(round(round(m / bin_width) * bin_width, 4) for m in above))
    n_obs  = [sum(1 for m in above if m >= bv) for bv in bin_vals]
    n_pred = [10 ** (a - b * bv) for bv in bin_vals]
    ss_res = sum((o - p) ** 2 for o, p in zip(n_obs, n_pred))
    mean_o = sum(n_obs) / len(n_obs)
    ss_tot = sum((o - mean_o) ** 2 for o in n_obs)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else None

    return {
        "b_value":             round(b, 3),
        "b_value_uncertainty": round(b_unc, 3),
        "a_value":             round(a, 3),
        "mc":                  round(mc, 2),
        "n_events":            n,
        "n_events_total":      len(magnitudes),
        "mean_magnitude":      round(mean_m, 3),
        "r_squared":           round(r2, 4) if r2 is not None else None,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Per-station residual statistics
# ──────────────────────────────────────────────────────────────────────────────

def compute_station_residuals(results: List[Dict]) -> List[Dict]:
    """
    Aggregate per-station time residuals across all events.

    Returns list of dicts, one per (network, station, phase):
        station_network, station_code, phase, n_arrivals, n_used,
        mean_residual, std_residual, min_residual, max_residual, mean_distance
    """
    residuals:  dict[tuple, list[float]] = defaultdict(list)
    distances:  dict[tuple, list[float]] = defaultdict(list)
    used_count: dict[tuple, int]         = defaultdict(int)

    for result in results:
        for rec in result.get("records", []):
            net   = rec.get("station_network", "")
            sta   = rec.get("station_code", "")
            phase = rec.get("phase", "?")
            res   = rec.get("arrival_residual")
            dist  = rec.get("arrival_distance")
            used  = rec.get("arrival_time_used")
            key   = (net, sta, phase)
            if res is not None:
                residuals[key].append(float(res))
            if dist is not None:
                distances[key].append(float(dist))
            if used is True:
                used_count[key] += 1

    rows: list[dict] = []
    for (net, sta, phase), res_list in sorted(residuals.items()):
        n     = len(res_list)
        mean  = sum(res_list) / n
        std   = math.sqrt(sum((r - mean) ** 2 for r in res_list) / n) if n > 1 else 0.0
        dists = distances[(net, sta, phase)]
        rows.append({
            "station_network": net,
            "station_code":    sta,
            "phase":           phase,
            "n_arrivals":      n,
            "n_used":          used_count[(net, sta, phase)],
            "mean_residual":   round(mean, 4),
            "std_residual":    round(std, 4),
            "min_residual":    round(min(res_list), 4),
            "max_residual":    round(max(res_list), 4),
            "mean_distance":   round(sum(dists) / len(dists), 2) if dists else None,
        })
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# Network summary report
# ──────────────────────────────────────────────────────────────────────────────

def compute_network_report(results: List[Dict]) -> Dict[str, Any]:
    """Compute a comprehensive catalog/network summary dict."""
    magnitudes: list[float] = []
    depths:     list[float] = []
    latitudes:  list[float] = []
    longitudes: list[float] = []
    timestamps: list[float] = []
    agencies:   set[str]    = set()
    networks:   set[str]    = set()
    stations:   set[str]    = set()
    phase_counts: dict[str, int] = defaultdict(int)
    mag_types:    dict[str, int] = defaultdict(int)

    for result in results:
        records = result.get("records", [])
        if not records:
            continue
        ref = records[0]

        if (mag := ref.get("event_magnitude_value")) is not None:
            magnitudes.append(float(mag))
            mag_types[str(ref.get("event_magnitude_type") or "?")] += 1
        if (dep := ref.get("event_depth")) is not None:
            depths.append(float(dep))
        if (lat := ref.get("event_latitude")) is not None:
            latitudes.append(float(lat))
        if (lon := ref.get("event_longitude")) is not None:
            longitudes.append(float(lon))
        if (ts := ref.get("event_timestamp")) is not None:
            timestamps.append(float(ts))
        if (ag := ref.get("event_agency")):
            agencies.add(str(ag))

        for rec in records:
            net = rec.get("station_network", "")
            sta = rec.get("station_code", "")
            if net and sta:
                networks.add(net)
                stations.add(f"{net}.{sta}")
            phase_counts[rec.get("phase", "?")] += 1

    def _stat(vals: list[float]) -> dict:
        if not vals:
            return {}
        return {
            "min":   round(min(vals), 3),
            "max":   round(max(vals), 3),
            "mean":  round(sum(vals) / len(vals), 3),
            "count": len(vals),
        }

    gr = compute_b_value(magnitudes) if len(magnitudes) >= 5 else None

    return {
        "n_events":      len(results),
        "n_records":     sum(r.get("stationCount", 0) for r in results),
        "n_networks":    len(networks),
        "n_stations":    len(stations),
        "agencies":      sorted(agencies),
        "networks":      sorted(networks),
        "time_start":    (datetime.fromtimestamp(min(timestamps), tz=timezone.utc).isoformat()
                          if timestamps else None),
        "time_end":      (datetime.fromtimestamp(max(timestamps), tz=timezone.utc).isoformat()
                          if timestamps else None),
        "magnitude":     _stat(magnitudes),
        "depth_km":      _stat(depths),
        "latitude":      _stat(latitudes),
        "longitude":     _stat(longitudes),
        "magnitude_types": dict(mag_types),
        "phase_counts":    dict(sorted(phase_counts.items(), key=lambda x: -x[1])),
        "gutenberg_richter": gr,
    }


def format_network_report(report: Dict[str, Any]) -> str:
    """Format the network report dict as human-readable text."""
    lines = [
        "SeisComP Catalog Statistics",
        "=" * 50,
        "",
        f"Events    : {report.get('n_events', 0)}",
        f"Records   : {report.get('n_records', 0)}",
        f"Networks  : {report.get('n_networks', 0)}  "
        f"({', '.join(report.get('networks', [])[:10])})",
        f"Stations  : {report.get('n_stations', 0)}",
        f"Agencies  : {', '.join(report.get('agencies', []))}",
        "",
        "TIME RANGE",
        f"  Start : {report.get('time_start') or 'n/a'}",
        f"  End   : {report.get('time_end') or 'n/a'}",
        "",
    ]

    for label, key in (
        ("MAGNITUDE",   "magnitude"),
        ("DEPTH (km)",  "depth_km"),
        ("LATITUDE",    "latitude"),
        ("LONGITUDE",   "longitude"),
    ):
        st = report.get(key, {})
        if st:
            lines.append(
                f"{label:<14} "
                f"min={st.get('min','?'):>8}  "
                f"max={st.get('max','?'):>8}  "
                f"mean={st.get('mean','?'):>8}"
            )
    lines.append("")

    mt = report.get("magnitude_types", {})
    if mt:
        lines.append("MAGNITUDE TYPES")
        for t, n in sorted(mt.items(), key=lambda x: -x[1]):
            lines.append(f"  {t:<6}  {n} events")
        lines.append("")

    gr = report.get("gutenberg_richter")
    if gr and gr.get("b_value") is not None:
        lines += [
            "GUTENBERG-RICHTER  (maximum likelihood)",
            f"  b-value  : {gr['b_value']:.3f} ± {gr.get('b_value_uncertainty', '?')}",
            f"  a-value  : {gr.get('a_value', '?')}",
            f"  Mc       : {gr.get('mc', '?')}  (maximum curvature)",
            f"  N(≥ Mc)  : {gr.get('n_events', '?')} / {gr.get('n_events_total', '?')} total",
            f"  R²       : {gr.get('r_squared', 'n/a')}",
            "",
        ]

    pc = report.get("phase_counts", {})
    if pc:
        lines.append("PHASE COUNTS (top 15)")
        for ph, n in list(pc.items())[:15]:
            lines.append(f"  {ph:<10}  {n:>7}")
        lines.append("")

    return "\n".join(lines)
