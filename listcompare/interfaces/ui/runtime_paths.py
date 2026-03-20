"""Runtime storage paths for data that should survive between app launches."""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

APP_NAME = "ListCompare"
DATA_DIR_ENV_VAR = "LISTCOMPARE_DATA_DIR"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PERSISTENT_FILE_NAMES = (
    "supplier_index.txt",
    "brand_index.txt",
    "ui_settings.json",
    "supplier_transform_profiles.json",
)
SHARED_SYNC_FILE_NAMES = (
    "supplier_index.txt",
    "brand_index.txt",
    "supplier_transform_profiles.json",
)


def _default_data_dir(
    *,
    env: Mapping[str, str] | None = None,
    os_name: str | None = None,
    home_dir: Path | None = None,
) -> Path:
    env_map = os.environ if env is None else env
    current_os_name = os.name if os_name is None else os_name
    current_home_dir = Path.home() if home_dir is None else home_dir

    override = str(env_map.get(DATA_DIR_ENV_VAR, "")).strip()
    if override != "":
        return Path(override).expanduser().resolve()

    if current_os_name == "nt":
        local_app_data = str(env_map.get("LOCALAPPDATA", "")).strip()
        base_dir = (
            Path(local_app_data).expanduser()
            if local_app_data != ""
            else current_home_dir / "AppData" / "Local"
        )
        return (base_dir / APP_NAME).resolve()

    xdg_data_home = str(env_map.get("XDG_DATA_HOME", "")).strip()
    if xdg_data_home != "":
        return (Path(xdg_data_home).expanduser() / APP_NAME).resolve()

    return (current_home_dir / ".local" / "share" / APP_NAME).resolve()


def app_data_dir() -> Path:
    """Return the persistent app-data directory for the current runtime."""

    return _default_data_dir()


def supplier_index_path() -> Path:
    """Return the persisted supplier index file path."""

    return app_data_dir() / "supplier_index.txt"


def brand_index_path() -> Path:
    """Return the persisted brand index file path."""

    return app_data_dir() / "brand_index.txt"


def ui_settings_path() -> Path:
    """Return the persisted UI settings file path."""

    return app_data_dir() / "ui_settings.json"


def supplier_transform_profiles_path() -> Path:
    """Return the persisted supplier transform profile file path."""

    return app_data_dir() / "supplier_transform_profiles.json"


def shared_sync_config_path() -> Path:
    """Return the local config path for the optional shared sync folder."""

    return app_data_dir() / "shared_sync_config.json"


def shared_sync_base_dir() -> Path:
    """Return the local directory used to track the last synced shared payloads."""

    return app_data_dir() / "shared_sync_base"


def _resource_root(*, project_root: Path = PROJECT_ROOT) -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return project_root


def _seed_source_roots(*, data_dir: Path, project_root: Path = PROJECT_ROOT) -> list[Path]:
    resolved_data_dir = data_dir.resolve()
    roots: list[Path] = []
    seen: set[str] = set()

    for candidate in (project_root, _resource_root(project_root=project_root)):
        resolved_candidate = candidate.resolve()
        candidate_key = str(resolved_candidate).casefold()
        if resolved_candidate == resolved_data_dir or candidate_key in seen:
            continue
        seen.add(candidate_key)
        roots.append(resolved_candidate)

    return roots


def _initialize_runtime_storage(
    *,
    data_dir: Path,
    source_roots: Sequence[Path],
    file_names: Sequence[str] = PERSISTENT_FILE_NAMES,
) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)

    for file_name in file_names:
        target_path = data_dir / file_name
        if target_path.exists():
            continue

        for source_root in source_roots:
            source_path = source_root / file_name
            if source_path.exists():
                shutil.copyfile(source_path, target_path)
                break


def ensure_runtime_storage_initialized() -> None:
    """Create the runtime data directory and seed missing persistent files."""

    data_dir = app_data_dir()
    _initialize_runtime_storage(
        data_dir=data_dir,
        source_roots=_seed_source_roots(data_dir=data_dir),
    )
