#!/usr/bin/env python3
"""
SeisComP Station Data Extractor
================================
CLI and GUI tool for extracting station / arrival data from SeisComP XML files.

Usage examples
--------------
# GUI (default when no input files are given)
python sc_extractor.py
python sc_extractor.py --gui

# Single file → CSV
python sc_extractor.py event.xml

# Batch (glob) → CSV + GeoJSON + ZIP
python sc_extractor.py *.xml -o results/ --format both --zip

# Spatial + quality filters
python sc_extractor.py *.xml --min-mag 3.0 --max-mag 7.0 \\
    --bbox -40,0,110,160 --max-gap 200 --min-phases 8 --max-rms 1.0

# Time-range filter
python sc_extractor.py *.xml --start-time 2021-01-01T00:00:00 --end-time 2021-12-31T23:59:59

# Radius filter (centre + radius in km)
python sc_extractor.py *.xml --radius -23.5,133.8,500

# Extended output formats
python sc_extractor.py *.xml --format hypo71 -o output/
python sc_extractor.py *.xml --format nordic  -o output/
python sc_extractor.py *.xml --format sqlite  -o output/
python sc_extractor.py *.xml --format parquet -o output/

# Print catalog statistics
python sc_extractor.py *.xml --stats

# Save / load presets
python sc_extractor.py --save-preset my_setup \\
    --fields eventID,event_latitude,phase --min-mag 2.0 --format csv
python sc_extractor.py *.xml --preset my_setup
"""
from __future__ import annotations

import argparse
import glob
import sys
from datetime import date
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from core.fields import ALL_FIELDS, RECOMMENDED_FIELDS, FIELD_CATEGORIES
from core.filters import FilterConfig
from core.parser import SeisCompParser
from core.exporters import (
    generate_csv, generate_geojson,
    export_to_zip, export_single_event, create_summary,
)
from core.presets import (
    PRESETS_DIR, load_preset, save_preset, list_presets,
)


# ──────────────────────────────────────────────────────────────────────────────
# CLI helpers
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_inputs(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()
    for pat in patterns:
        for match in glob.glob(pat, recursive=True):
            p = Path(match).resolve()
            key = str(p)
            if key not in seen and p.suffix.lower() == ".xml":
                paths.append(p)
                seen.add(key)
    return paths


def _print_progress(current: int, total: int, msg: str):
    bar_len = 30
    filled = int(bar_len * current / max(total, 1))
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\r  [{bar}] {current}/{total}  {msg:<50}", end="", flush=True)


def _field_list_from_arg(raw: str) -> list[str]:
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    bad  = [k for k in keys if k not in ALL_FIELDS]
    if bad:
        print(f"[WARNING] Unknown field keys (ignored): {', '.join(bad)}")
    return [k for k in keys if k in ALL_FIELDS]


def _list_fields_and_exit():
    print("\nAvailable output fields\n" + "=" * 44)
    for cat_name, cat_data in FIELD_CATEGORIES.items():
        print(f"\n  {cat_name}")
        for key, label in cat_data["fields"].items():
            star = " *" if key in RECOMMENDED_FIELDS else ""
            print(f"    {key:<45} {label}{star}")
    print("\n  (* = recommended preset)")
    sys.exit(0)


def _parse_bbox(s: str) -> tuple:
    """'lat_min,lat_max,lon_min,lon_max' → 4-tuple of floats."""
    parts = [x.strip() for x in s.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            "bbox must be lat_min,lat_max,lon_min,lon_max (4 values)"
        )
    try:
        return tuple(float(x) for x in parts)
    except ValueError:
        raise argparse.ArgumentTypeError("bbox values must be numbers")


def _parse_radius(s: str) -> tuple:
    """'center_lat,center_lon,radius_km' → (lat, lon, km)."""
    parts = [x.strip() for x in s.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            "radius must be center_lat,center_lon,radius_km"
        )
    try:
        return tuple(float(x) for x in parts)
    except ValueError:
        raise argparse.ArgumentTypeError("radius values must be numbers")


# ──────────────────────────────────────────────────────────────────────────────
# CLI main
# ──────────────────────────────────────────────────────────────────────────────

def run_cli(args: argparse.Namespace):
    input_paths = _resolve_inputs(args.inputs)

    if args.save_preset:
        _cli_save_preset(args)
        return

    if not input_paths:
        print("[ERROR] No XML files found. Use --gui to open the GUI or "
              "pass file paths / glob patterns.", file=sys.stderr)
        sys.exit(1)

    # ── Build filter config ────────────────────────────────
    phases = FilterConfig.parse_phase_string(args.phases or "all")

    bbox = None
    if args.bbox:
        bbox = _parse_bbox(args.bbox)

    center_lat = center_lon = radius_km = None
    if args.radius:
        center_lat, center_lon, radius_km = _parse_radius(args.radius)

    filters = FilterConfig(
        arrivals=args.arrivals,
        min_magnitude=args.min_mag if args.min_mag and args.min_mag > 0 else None,
        max_magnitude=args.max_mag if args.max_mag and args.max_mag > 0 else None,
        max_distance=args.max_dist if args.max_dist and args.max_dist > 0 else None,
        phases=phases,
        bbox=bbox,
        center_lat=center_lat,
        center_lon=center_lon,
        radius_km=radius_km,
        start_time=args.start_time or None,
        end_time=args.end_time or None,
        max_azimuthal_gap=args.max_gap if args.max_gap and args.max_gap > 0 else None,
        min_used_phases=args.min_phases if args.min_phases and args.min_phases > 0 else None,
        max_rms=args.max_rms if args.max_rms and args.max_rms > 0 else None,
        max_depth_uncertainty=args.max_dep_unc if args.max_dep_unc and args.max_dep_unc > 0 else None,
    )

    # ── Load preset ────────────────────────────────────────
    selected_fields: list[str] = RECOMMENDED_FIELDS[:]
    fmt = args.format

    if args.preset:
        preset_data = _load_preset_by_name(args.preset)
        if preset_data:
            if "filters" in preset_data:
                filters = FilterConfig.from_dict(preset_data["filters"])
            if "fields" in preset_data:
                selected_fields = preset_data["fields"]
            if "format" in preset_data:
                fmt = preset_data["format"]
            print(f"  Preset '{preset_data.get('name', args.preset)}' loaded.")
        else:
            print(f"[WARNING] Preset '{args.preset}' not found; using defaults.")

    if args.fields:
        selected_fields = _field_list_from_arg(args.fields)
        if not selected_fields:
            print("[ERROR] No valid fields specified.", file=sys.stderr)
            sys.exit(1)

    if not selected_fields:
        selected_fields = RECOMMENDED_FIELDS[:]

    output_dir = Path(args.output) if args.output else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Parse ──────────────────────────────────────────────
    parser = SeisCompParser()
    all_results: list[dict] = []

    print(f"\nProcessing {len(input_paths)} file(s)…")
    for i, path in enumerate(input_paths):
        _print_progress(i, len(input_paths), path.name)
        results = parser.parse_file(
            path, filters,
            progress_callback=lambda cur, tot, msg: None,
        )
        all_results.extend(results)
    _print_progress(len(input_paths), len(input_paths), "Done!")
    print()

    if not all_results:
        print("[WARNING] No events matched the current filters.")
        return

    total_records = sum(r.get("stationCount", 0) for r in all_results)
    versions      = sorted({r.get("schemaVersion", "?") for r in all_results})
    print(f"  {len(all_results)} event(s)  |  {total_records} records  |  "
          f"schema version(s): {', '.join(versions)}")

    # ── Statistics ─────────────────────────────────────────
    if args.stats:
        from core.stats import compute_network_report, format_network_report
        report = compute_network_report(all_results)
        print("\n" + format_network_report(report))

    # ── Export ──────────────────────────────────────────────
    today = date.today().isoformat()

    if fmt in ("csv", "geojson", "both"):
        if args.zip:
            zip_name = f"seiscomp_data_{today}_{fmt}_{len(all_results)}events.zip"
            zip_path = output_dir / zip_name
            export_to_zip(all_results, zip_path, fmt, selected_fields,
                          lambda d, t, m: _print_progress(d, t, m))
            print(f"\n  → {zip_path}")
        else:
            created_all: list[Path] = []
            for result in all_results:
                created_all.extend(export_single_event(result, output_dir, fmt, selected_fields))
            print(f"  → {len(created_all)} file(s) written to {output_dir}")

    elif fmt == "hypo71":
        from core.formats import generate_hypo71
        out = output_dir / f"seiscomp_{today}.pha"
        out.write_text(generate_hypo71(all_results), encoding="utf-8")
        print(f"  → {out}")

    elif fmt == "nordic":
        from core.formats import generate_nordic
        out = output_dir / f"seiscomp_{today}.nor"
        out.write_text(generate_nordic(all_results), encoding="utf-8")
        print(f"  → {out}")

    elif fmt == "sqlite":
        from core.formats import export_to_sqlite
        out = output_dir / f"seiscomp_{today}.db"
        export_to_sqlite(all_results, out, selected_fields)
        print(f"  → {out}")

    elif fmt == "parquet":
        from core.formats import export_to_parquet
        out = output_dir / f"seiscomp_{today}.parquet"
        export_to_parquet(all_results, out, selected_fields)
        print(f"  → {out}")

    # Summary (only for CSV/GeoJSON workflows)
    if fmt in ("csv", "geojson", "both"):
        summary_path = output_dir / "README_processing_summary.txt"
        summary_path.write_text(create_summary(all_results, fmt), encoding="utf-8")
        print(f"  → Summary: {summary_path}")


def _load_preset_by_name(name: str) -> Optional[dict]:
    for path in list_presets():
        if path.stem.lower() == name.lower():
            return load_preset(path)
    for path in list_presets():
        try:
            data = load_preset(path)
            if data.get("name", "").lower() == name.lower():
                return data
        except Exception:
            pass
    p = Path(name)
    if p.exists() and p.suffix == ".json":
        return load_preset(p)
    return None


def _cli_save_preset(args: argparse.Namespace):
    name   = args.save_preset
    phases = FilterConfig.parse_phase_string(args.phases or "all")
    filters = FilterConfig(
        arrivals=args.arrivals,
        min_magnitude=args.min_mag if args.min_mag and args.min_mag > 0 else None,
        max_magnitude=args.max_mag if args.max_mag and args.max_mag > 0 else None,
        max_distance=args.max_dist if args.max_dist and args.max_dist > 0 else None,
        phases=phases,
        max_azimuthal_gap=args.max_gap if args.max_gap and args.max_gap > 0 else None,
        min_used_phases=args.min_phases if args.min_phases and args.min_phases > 0 else None,
        max_rms=args.max_rms if args.max_rms and args.max_rms > 0 else None,
        max_depth_uncertainty=args.max_dep_unc if args.max_dep_unc and args.max_dep_unc > 0 else None,
    )
    fields = _field_list_from_arg(args.fields) if args.fields else RECOMMENDED_FIELDS[:]
    safe   = name.replace(" ", "_").replace("/", "_")
    path   = PRESETS_DIR / f"{safe}.json"
    save_preset(path, name, filters, fields, args.format)
    print(f"Preset '{name}' saved → {path}")


# ──────────────────────────────────────────────────────────────────────────────
# GUI entry
# ──────────────────────────────────────────────────────────────────────────────

def run_gui(preload_files: list[str] | None = None):
    try:
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import Qt
        from gui.main_window import MainWindow
    except ImportError as exc:
        print(f"[ERROR] PyQt5 is required for the GUI: {exc}", file=sys.stderr)
        print("        Install with:  pip install PyQt5", file=sys.stderr)
        sys.exit(1)

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("SeisComP Extractor")
    app.setOrganizationName("SeisComp")

    window = MainWindow()
    window.show()

    if preload_files:
        window._on_files_dropped(preload_files)

    sys.exit(app.exec_())


# ──────────────────────────────────────────────────────────────────────────────
# Argument parser
# ──────────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sc_extractor",
        description="SeisComP XML → CSV / GeoJSON / HYPO71 / Nordic / SQLite / Parquet  (CLI + GUI)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python sc_extractor.py                              # open GUI
  python sc_extractor.py event.xml                    # single file → CSV
  python sc_extractor.py data/*.xml -o out/ --format both --zip
  python sc_extractor.py data/*.xml --min-mag 3.0 --max-gap 200 --min-phases 8
  python sc_extractor.py data/*.xml --bbox -40,0,110,160
  python sc_extractor.py data/*.xml --radius -23.5,133.8,500
  python sc_extractor.py data/*.xml --start-time 2021-01-01T00:00:00
  python sc_extractor.py data/*.xml --format hypo71 -o output/
  python sc_extractor.py data/*.xml --format sqlite  -o output/
  python sc_extractor.py data/*.xml --stats
  python sc_extractor.py --list-fields
""",
    )

    p.add_argument("inputs", nargs="*", metavar="FILE_OR_GLOB",
                   help="Input XML files or glob patterns. If omitted, opens GUI.")

    # Output
    out = p.add_argument_group("Output")
    out.add_argument("-o", "--output", metavar="DIR",
                     help="Output directory (default: current directory)")
    out.add_argument("--format",
                     choices=["csv", "geojson", "both",
                              "hypo71", "nordic", "sqlite", "parquet"],
                     default="csv",
                     help="Output format (default: csv)")
    out.add_argument("--zip", action="store_true",
                     help="Bundle CSV/GeoJSON output into a ZIP archive")
    out.add_argument("--stats", action="store_true",
                     help="Print catalog statistics (G-R b-value, per-station residuals, …)")

    # Filters — basic
    flt = p.add_argument_group("Filters — basic")
    flt.add_argument("--arrivals", choices=["all", "used", "unused"], default="all")
    flt.add_argument("--min-mag",  type=float, metavar="MAG")
    flt.add_argument("--max-mag",  type=float, metavar="MAG")
    flt.add_argument("--max-dist", type=float, metavar="DEG",
                     help="Max epicentral distance (°)")
    flt.add_argument("--phases",   metavar="P,S,…",
                     help="Comma-separated phase codes (default: all)")

    # Filters — spatial
    sp = p.add_argument_group("Filters — spatial")
    sp.add_argument("--bbox", metavar="LAT_MIN,LAT_MAX,LON_MIN,LON_MAX",
                    help="Keep events inside this bounding box")
    sp.add_argument("--radius", metavar="CENTER_LAT,CENTER_LON,RADIUS_KM",
                    help="Keep events within radius_km of center")

    # Filters — temporal
    tm = p.add_argument_group("Filters — temporal")
    tm.add_argument("--start-time", metavar="ISO",
                    help="Keep events on or after this time (YYYY-MM-DDTHH:MM:SS)")
    tm.add_argument("--end-time",   metavar="ISO",
                    help="Keep events on or before this time")

    # Filters — quality
    qu = p.add_argument_group("Filters — quality")
    qu.add_argument("--max-gap",     type=float, metavar="DEG",
                    help="Max azimuthal gap (°)")
    qu.add_argument("--min-phases",  type=int,   metavar="N",
                    help="Min number of used phases")
    qu.add_argument("--max-rms",     type=float, metavar="S",
                    help="Max RMS residual (s)")
    qu.add_argument("--max-dep-unc", type=float, metavar="KM",
                    help="Max depth uncertainty (km)")

    # Fields
    fld = p.add_argument_group("Fields")
    fld.add_argument("--fields", metavar="KEY,KEY,…",
                     help="Comma-separated output field keys (see --list-fields)")
    fld.add_argument("--list-fields", action="store_true",
                     help="Print all available field keys and exit")

    # Presets
    pre = p.add_argument_group("Presets")
    pre.add_argument("--preset",      metavar="NAME")
    pre.add_argument("--save-preset", metavar="NAME")
    pre.add_argument("--list-presets", action="store_true")

    p.add_argument("--gui", action="store_true",
                   help="Launch the GUI (even if input files are provided)")

    return p


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = _build_parser()
    args   = parser.parse_args()

    if args.list_fields:
        _list_fields_and_exit()

    if args.list_presets:
        presets = list_presets()
        if not presets:
            print("No presets saved yet.")
        else:
            print("Saved presets:")
            for p in presets:
                try:
                    d = load_preset(p)
                    print(f"  {d.get('name', p.stem):<30}  "
                          f"{len(d.get('fields',[]))} fields  |  "
                          f"format: {d.get('format','?')}  |  {p}")
                except Exception:
                    print(f"  {p.stem}  (unreadable)")
        sys.exit(0)

    if args.gui or not args.inputs:
        preload = _resolve_inputs(args.inputs) if args.inputs else []
        run_gui([str(p) for p in preload])
    else:
        run_cli(args)


if __name__ == "__main__":
    main()
