from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


def load_shared_sync_config(path: Path) -> tuple[dict[str, str], Optional[str]]:
    default_config = {"shared_folder": ""}
    if not path.exists():
        return default_config, None

    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, dict):
            raise ValueError("shared_sync_config.json måste innehålla ett JSON-objekt.")
        shared_folder = str(raw.get("shared_folder", "")).strip()
        return {"shared_folder": shared_folder}, None
    except Exception as exc:
        return default_config, str(exc)


def save_shared_sync_config(path: Path, *, shared_folder: str) -> Optional[str]:
    payload = {
        "shared_folder": str(shared_folder).strip(),
    }
    try:
        parent = getattr(path, "parent", None)
        if parent is not None and hasattr(parent, "mkdir"):
            parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return None
    except Exception as exc:
        return str(exc)
