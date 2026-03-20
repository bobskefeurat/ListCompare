"""Helpers for synchronizing selected app data with an optional shared folder."""

from __future__ import annotations

import string
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from ....core.suppliers.profile import normalized_profiles_dict as _normalized_profiles_dict
from ..io.index_names import _merge_supplier_lists
from ..persistence import index_store as _index_store
from ..persistence import profile_store as _profile_store
from ..persistence import shared_sync_store as _shared_sync_store
from ..runtime_paths import (
    SHARED_SYNC_FILE_NAMES,
    brand_index_path as _brand_index_path,
    shared_sync_base_dir as _shared_sync_base_dir,
    shared_sync_config_path as _shared_sync_config_path,
    supplier_index_path as _supplier_index_path,
    supplier_transform_profiles_path as _supplier_transform_profiles_path,
)

SUPPLIER_INDEX_FILE_NAME = "supplier_index.txt"
BRAND_INDEX_FILE_NAME = "brand_index.txt"
PROFILES_FILE_NAME = "supplier_transform_profiles.json"

SharedSyncTarget = str

_MISSING = object()


@dataclass(frozen=True)
class SharedSyncStatus:
    level: str
    message: str
    shared_folder: str
    profile_conflicts: tuple[str, ...] = ()


def _validate_shared_sync_folder(shared_folder: str) -> tuple[str, Optional[str]]:
    normalized_folder = str(shared_folder).strip()
    if normalized_folder == "":
        return "", None

    try:
        resolved_folder = Path(normalized_folder).expanduser().resolve()
    except Exception as exc:
        return "", f"Kunde inte tolka delad synkmapp: {exc}"

    if not resolved_folder.exists():
        return "", f"Delad synkmapp finns inte: {resolved_folder}"
    if not resolved_folder.is_dir():
        return "", f"Delad synkmapp är inte en mapp: {resolved_folder}"
    return str(resolved_folder), None


def load_configured_shared_folder() -> tuple[str, Optional[str]]:
    config, error = _shared_sync_store.load_shared_sync_config(_shared_sync_config_path())
    return str(config.get("shared_folder", "")).strip(), error


def save_configured_shared_folder(shared_folder: str) -> Optional[str]:
    normalized_folder, validation_error = _validate_shared_sync_folder(shared_folder)
    if validation_error:
        return validation_error
    return _shared_sync_store.save_shared_sync_config(
        _shared_sync_config_path(),
        shared_folder=normalized_folder,
    )


def resolve_shared_sync_folder(
    *,
    folder_name: str = "ListCompareShared",
    auto_configure: bool = True,
) -> tuple[str, Optional[str], bool]:
    configured_folder, config_error = load_configured_shared_folder()
    if config_error:
        return "", config_error, False

    normalized_configured_folder, validation_error = _validate_shared_sync_folder(configured_folder)
    if validation_error:
        return "", validation_error, False
    if normalized_configured_folder:
        return normalized_configured_folder, None, False
    if not auto_configure:
        return "", None, False

    candidates = find_shared_sync_folder_candidates(folder_name=folder_name)
    if len(candidates) != 1:
        return "", None, False

    detected_folder = candidates[0]
    save_error = save_configured_shared_folder(detected_folder)
    if save_error:
        return "", save_error, False
    return detected_folder, None, True


def find_shared_sync_folder_candidates(*, folder_name: str = "ListCompareShared") -> list[str]:
    normalized_folder_name = str(folder_name).strip() or "ListCompareShared"
    candidates: list[str] = []
    seen: set[str] = set()

    def add_candidate(path: Path) -> None:
        try:
            resolved = path.expanduser().resolve()
        except Exception:
            return
        if not resolved.exists() or not resolved.is_dir():
            return
        candidate_text = str(resolved)
        candidate_key = candidate_text.casefold()
        if candidate_key in seen:
            return
        seen.add(candidate_key)
        candidates.append(candidate_text)

    configured_folder, _error = load_configured_shared_folder()
    if configured_folder:
        add_candidate(Path(configured_folder))

    for drive_letter in string.ascii_uppercase:
        drive_root = Path(f"{drive_letter}:\\")
        if not drive_root.exists():
            continue
        add_candidate(drive_root / "Min enhet" / normalized_folder_name)
        add_candidate(drive_root / "My Drive" / normalized_folder_name)
        add_candidate(drive_root / normalized_folder_name)

    home_dir = Path.home()
    add_candidate(home_dir / "Google Drive" / "Min enhet" / normalized_folder_name)
    add_candidate(home_dir / "Google Drive" / "My Drive" / normalized_folder_name)
    add_candidate(home_dir / "Google Drive" / normalized_folder_name)

    return sorted(candidates, key=lambda value: value.casefold())


def sync_shared_files(
    *,
    targets: tuple[SharedSyncTarget, ...] = SHARED_SYNC_FILE_NAMES,
) -> SharedSyncStatus:
    shared_folder, config_error, auto_configured = resolve_shared_sync_folder()
    if config_error:
        return SharedSyncStatus(
            level="error",
            message=f"Kunde inte läsa delad synk-konfiguration: {config_error}",
            shared_folder="",
        )

    normalized_targets = tuple(
        target for target in targets if target in SHARED_SYNC_FILE_NAMES
    )
    if not normalized_targets:
        return SharedSyncStatus(
            level="disabled",
            message="Ingen delad synk kördes.",
            shared_folder=shared_folder,
        )

    if shared_folder == "":
        return SharedSyncStatus(
            level="disabled",
            message="Ingen delad synkmapp vald.",
            shared_folder="",
        )

    try:
        shared_root = Path(shared_folder).expanduser()
        base_dir = _shared_sync_base_dir()
        base_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return SharedSyncStatus(
            level="error",
            message=f"Kunde inte använda delad synkmapp: {exc}",
            shared_folder=shared_folder,
        )

    try:
        if SUPPLIER_INDEX_FILE_NAME in normalized_targets:
            _sync_names_file(
                local_path=_supplier_index_path(),
                shared_path=shared_root / SUPPLIER_INDEX_FILE_NAME,
                base_path=base_dir / SUPPLIER_INDEX_FILE_NAME,
                load_names=_load_supplier_names,
                save_names=_save_supplier_names,
            )
        if BRAND_INDEX_FILE_NAME in normalized_targets:
            _sync_names_file(
                local_path=_brand_index_path(),
                shared_path=shared_root / BRAND_INDEX_FILE_NAME,
                base_path=base_dir / BRAND_INDEX_FILE_NAME,
                load_names=_load_brand_names,
                save_names=_save_brand_names,
            )

        profile_conflicts: tuple[str, ...] = ()
        if PROFILES_FILE_NAME in normalized_targets:
            profile_conflicts = _sync_profiles_file(
                local_path=_supplier_transform_profiles_path(),
                shared_path=shared_root / PROFILES_FILE_NAME,
                base_path=base_dir / PROFILES_FILE_NAME,
            )
    except Exception as exc:
        return SharedSyncStatus(
            level="error",
            message=f"Kunde inte synka delad mapp: {exc}",
            shared_folder=shared_folder,
        )

    if profile_conflicts:
        joined_names = ", ".join(profile_conflicts)
        return SharedSyncStatus(
            level="warning",
            message=(
                "Delad synk hittade profilkonflikter för: "
                f"{joined_names}. Synka manuellt innan fler profiländringar sparas."
            ),
            shared_folder=shared_folder,
            profile_conflicts=profile_conflicts,
        )

    success_message = f"Delad synk klar mot {shared_folder}."
    if auto_configured:
        success_message = f"Hittade och aktiverade delad synkmapp automatiskt: {shared_folder}."
    return SharedSyncStatus(
        level="success",
        message=success_message,
        shared_folder=shared_folder,
    )


def _load_supplier_names(path: Path) -> list[str]:
    if not path.exists():
        return []
    values, error = _index_store.load_suppliers_from_index(path)
    if error:
        raise ValueError(error)
    return values


def _save_supplier_names(path: Path, values: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _index_store.save_suppliers_to_index(path, values)


def _load_brand_names(path: Path) -> list[str]:
    if not path.exists():
        return []
    values, error = _index_store.load_brands_from_index(path)
    if error:
        raise ValueError(error)
    return values


def _save_brand_names(path: Path, values: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _index_store.save_brands_to_index(path, values)


def _load_profiles(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    values, error = _profile_store.load_profiles(path)
    if error:
        raise ValueError(error)
    return _normalized_profiles_dict(values)


def _save_profiles(path: Path, values: dict[str, dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    error = _profile_store.save_profiles(path, profiles=values)
    if error:
        raise ValueError(error)


def _should_write_synced_payload(*, path: Path, current_value: object, merged_value: object) -> bool:
    return (not path.exists()) or current_value != merged_value


def _sync_names_file(
    *,
    local_path: Path,
    shared_path: Path,
    base_path: Path,
    load_names: Callable[[Path], list[str]],
    save_names: Callable[[Path, list[str]], None],
) -> None:
    local_values = load_names(local_path)
    shared_values = load_names(shared_path)
    merged_values, _new_names = _merge_supplier_lists(local_values, shared_values)
    base_values = load_names(base_path)

    if _should_write_synced_payload(
        path=local_path,
        current_value=local_values,
        merged_value=merged_values,
    ):
        save_names(local_path, merged_values)
    if _should_write_synced_payload(
        path=shared_path,
        current_value=shared_values,
        merged_value=merged_values,
    ):
        save_names(shared_path, merged_values)
    if _should_write_synced_payload(
        path=base_path,
        current_value=base_values,
        merged_value=merged_values,
    ):
        save_names(base_path, merged_values)


def _sync_profiles_file(
    *,
    local_path: Path,
    shared_path: Path,
    base_path: Path,
) -> tuple[str, ...]:
    local_profiles = _load_profiles(local_path)
    shared_profiles = _load_profiles(shared_path)
    base_profiles = _load_profiles(base_path)

    merged_profiles, conflicts = _merge_profiles(
        base_profiles=base_profiles,
        local_profiles=local_profiles,
        shared_profiles=shared_profiles,
    )
    if conflicts:
        return conflicts

    if _should_write_synced_payload(
        path=local_path,
        current_value=local_profiles,
        merged_value=merged_profiles,
    ):
        _save_profiles(local_path, merged_profiles)
    if _should_write_synced_payload(
        path=shared_path,
        current_value=shared_profiles,
        merged_value=merged_profiles,
    ):
        _save_profiles(shared_path, merged_profiles)
    if _should_write_synced_payload(
        path=base_path,
        current_value=base_profiles,
        merged_value=merged_profiles,
    ):
        _save_profiles(base_path, merged_profiles)
    return ()


def _merge_profiles(
    *,
    base_profiles: dict[str, dict[str, object]],
    local_profiles: dict[str, dict[str, object]],
    shared_profiles: dict[str, dict[str, object]],
) -> tuple[dict[str, dict[str, object]], tuple[str, ...]]:
    merged_profiles: dict[str, dict[str, object]] = {}
    conflicts: list[str] = []
    all_supplier_names = sorted(
        set(base_profiles.keys()) | set(local_profiles.keys()) | set(shared_profiles.keys()),
        key=lambda value: value.casefold(),
    )
    for supplier_name in all_supplier_names:
        base_profile = base_profiles.get(supplier_name, _MISSING)
        local_profile = local_profiles.get(supplier_name, _MISSING)
        shared_profile = shared_profiles.get(supplier_name, _MISSING)

        if local_profile == shared_profile:
            if local_profile is not _MISSING:
                merged_profiles[supplier_name] = local_profile
            continue
        if local_profile == base_profile:
            if shared_profile is not _MISSING:
                merged_profiles[supplier_name] = shared_profile
            continue
        if shared_profile == base_profile:
            if local_profile is not _MISSING:
                merged_profiles[supplier_name] = local_profile
            continue

        conflicts.append(supplier_name)

    return merged_profiles, tuple(conflicts)
