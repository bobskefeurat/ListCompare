from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ....core.suppliers.profile import (
    build_profiles_payload as _build_profiles_payload,
    parse_profiles_payload as _parse_profiles_payload,
)


def load_profiles(path: Path) -> tuple[dict[str, dict[str, object]], Optional[str]]:
    if not path.exists():
        return {}, None

    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        return _parse_profiles_payload(raw), None
    except Exception as exc:
        return {}, str(exc)


def save_profiles(
    path: Path,
    *,
    profiles: dict[str, dict[str, object]],
) -> Optional[str]:
    payload = _build_profiles_payload(profiles)
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return None
    except Exception as exc:
        return str(exc)
