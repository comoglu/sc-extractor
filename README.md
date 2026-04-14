# sc-extractor — SeisComP Station Data Extractor

A Python CLI + PyQt5 GUI tool for extracting arrival/phase data from SeisComP XML files across schema versions 0.5–0.14.

## Features

- **Schema support**: versions 0.5 – 0.14 (namespace-aware parsing, forward-compatible)
- **Arrivals-only files**: fallback pickID string decoder for files without `<pick>` elements
- **130+ output fields** across 11 categories (event, origin, magnitude, quality, station, pick, arrival, amplitude, S-P times, velocities, statistics)
- **Calculated fields**: S-P time, Vp/Vs ratio, apparent velocities, distance in km, location quality score (0–100), depth constraint type, predicted travel times
- **Output formats**: CSV, GeoJSON, HYPO71 phase file, Nordic/SEISAN, SQLite, Parquet
- **ZIP export** with per-event CSV + GeoJSON files
- **Filters**: magnitude range, distance, phase, bounding box, radius (km), time range, azimuthal gap, used phases, RMS, depth uncertainty
- **Catalog statistics**: Gutenberg-Richter b-value (max. likelihood), magnitude of completeness Mc (max. curvature), per-station residual table, network report
- **Preset system**: save/load named filter+field+format configurations
- **Dark/light theme** toggle in the GUI
- **AGPL-3.0** license

## Installation

```bash
pip install PyQt5          # GUI only
pip install pyarrow        # Parquet export (optional)
```

No other external dependencies — all other libraries are from the Python standard library.

## Quick start

```bash
# Launch GUI
python sc_extractor.py

# Single file → CSV
python sc_extractor.py event.xml

# Batch → CSV + GeoJSON + ZIP
python sc_extractor.py data/*.xml -o results/ --format both --zip

# Quality + spatial filters
python sc_extractor.py data/*.xml \
    --min-mag 2.5 --max-gap 200 --min-phases 6 --max-rms 1.5 \
    --bbox -40,0,110,160

# Radius filter (500 km from centre)
python sc_extractor.py data/*.xml --radius -23.5,133.8,500

# Time range
python sc_extractor.py data/*.xml \
    --start-time 2021-01-01T00:00:00 --end-time 2021-12-31T23:59:59

# Extended formats
python sc_extractor.py data/*.xml --format hypo71 -o output/
python sc_extractor.py data/*.xml --format nordic  -o output/
python sc_extractor.py data/*.xml --format sqlite  -o output/
python sc_extractor.py data/*.xml --format parquet -o output/

# Print catalog statistics (G-R b-value, Mc, per-station residuals)
python sc_extractor.py data/*.xml --stats

# List all available output fields
python sc_extractor.py --list-fields

# Save / load presets
python sc_extractor.py --save-preset my_setup \
    --fields eventID,event_latitude,event_longitude,phase,arrival_distance \
    --min-mag 2.0 --phases P,S --format csv

python sc_extractor.py data/*.xml --preset my_setup
```

## Project structure

```
sc_extractor.py         Entry point (CLI + GUI launcher)
core/
  schema.py             Namespace / schema version detection
  fields.py             All 130+ field definitions and categories
  filters.py            FilterConfig dataclass
  parser.py             SeisCompParser — namespace-aware XML extraction
  exporters.py          CSV, GeoJSON, ZIP exporters
  formats.py            HYPO71, Nordic, SQLite, Parquet exporters
  stats.py              Gutenberg-Richter, per-station residuals, network report
  presets.py            Preset save/load (~/.sc_extractor/presets/)
gui/
  main_window.py        Main PyQt5 window
  drop_zone.py          Drag-and-drop file zone
  field_selector.py     Collapsible category checkboxes
  filter_panel.py       Tabbed filter controls (Basic/Spatial/Temporal/Quality)
  results_panel.py      Results summary + per-event download cards
  stats_panel.py        Network report + station residuals table
  preset_dialog.py      Preset manager dialog
  styles.py             Light + dark QSS stylesheets
```

## Catalog statistics

Run `--stats` on the CLI or switch to the **Statistics** tab in the GUI after processing to see:

- Event/record/network/station counts and time range
- Magnitude, depth, lat/lon min/max/mean
- **Gutenberg-Richter b-value** (maximum likelihood estimator, Aki 1965) with uncertainty (Shi & Bolt 1982) and R²
- **Magnitude of completeness Mc** (maximum curvature method)
- Phase counts
- Per-station residual table: mean, std, min/max residual per (network, station, phase)

## Output fields (selected highlights)

| Field | Description |
|---|---|
| `location_quality_score` | Composite quality score 0–100 (gap + RMS + phases + min_dist) |
| `sp_time` | S-P time (s) |
| `vp_vs_ratio` | Vp/Vs ratio = ts/tp per station |
| `vp_estimate` | Apparent P velocity (km/s) |
| `vs_estimate` | Apparent S velocity (km/s) |
| `distance_km` | Epicentral distance (km) |
| `depth_constraint` | Origin depth constraint type |
| `station_magnitude_residual` | Station magnitude residual vs. network magnitude |
| `predicted_travel_time_p` | Predicted P travel time (observed − residual) |

## License

GNU Affero General Public License v3.0 — see [LICENSE](LICENSE).
