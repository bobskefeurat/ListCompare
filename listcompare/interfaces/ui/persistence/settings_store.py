from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .index_store import normalize_names


def load_ui_settings(path: Path) -> tuple[dict[str, list[str]], Optional[str]]:
    default_settings: dict[str, list[str]] = {"excluded_brands": []}
    if not path.exists():
        return default_settings, None

    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, dict):
            raise ValueError("ui_settings.json måste innehålla ett JSON-objekt.")

        raw_excluded = raw.get("excluded_brands", [])
        if not isinstance(raw_excluded, list):
            raise ValueError('Fältet "excluded_brands" måste vara en lista.')

        excluded_brands = normalize_names([str(name) for name in raw_excluded])
        return {"excluded_brands": excluded_brands}, None
    except Exception as exc:
        return default_settings, str(exc)


def save_ui_settings(path: Path, *, excluded_brands: list[str]) -> Optional[str]:
    payload = {"excluded_brands": normalize_names([str(name) for name in excluded_brands])}
    try:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return None
    except Exception as exc:
        return str(exc)
