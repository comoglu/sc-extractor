"""
Preset I/O — no PyQt5 dependency; safe to import in CLI or GUI contexts.
Presets are stored as JSON files in ~/.sc_extractor/presets/.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .filters import FilterConfig

PRESETS_DIR = Path.home() / ".sc_extractor" / "presets"


def _ensure_dir():
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)


def load_preset(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_preset(
    path: Path,
    name: str,
    filters: FilterConfig,
    fields: list[str],
    fmt: str,
):
    _ensure_dir()
    data = {
        "name":    name,
        "filters": filters.to_dict(),
        "fields":  fields,
        "format":  fmt,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def list_presets() -> list[Path]:
    _ensure_dir()
    return sorted(PRESETS_DIR.glob("*.json"))
