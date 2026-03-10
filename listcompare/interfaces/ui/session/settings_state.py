from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..persistence import settings_store as _settings_store


def load_ui_settings(path: Path) -> tuple[dict[str, list[str]], Optional[str]]:
    return _settings_store.load_ui_settings(path)


def save_ui_settings(path: Path, *, excluded_brands: list[str]) -> Optional[str]:
    return _settings_store.save_ui_settings(path, excluded_brands=excluded_brands)


def persist_excluded_brands_setting(
    session_state: dict[str, object],
    *,
    path: Path,
) -> None:
    save_error = save_ui_settings(
        path,
        excluded_brands=[str(name) for name in session_state.get("excluded_brands", [])],
    )
    session_state["ui_settings_save_error"] = save_error
    if save_error is None:
        session_state["ui_settings_load_error"] = None
