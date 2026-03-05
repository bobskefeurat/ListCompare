from __future__ import annotations

from pathlib import Path
from typing import Optional

from ...supplier_profile_utils import (
    load_supplier_transform_profiles as _load_supplier_transform_profiles,
    save_supplier_transform_profiles as _save_supplier_transform_profiles,
)


def load_profiles(path: Path) -> tuple[dict[str, dict[str, object]], Optional[str]]:
    return _load_supplier_transform_profiles(path)


def save_profiles(
    path: Path,
    *,
    profiles: dict[str, dict[str, object]],
) -> Optional[str]:
    return _save_supplier_transform_profiles(path, profiles=profiles)
