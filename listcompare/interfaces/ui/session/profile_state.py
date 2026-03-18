from __future__ import annotations

from typing import Optional

from ....core.suppliers.profile import (
    SUPPLIER_TRANSFORM_DEFAULT_FILTERS,
    normalize_supplier_transform_profile_details as _normalize_supplier_transform_profile_details,
    normalize_supplier_transform_profile_filters as _normalize_supplier_transform_profile_filters,
    normalize_supplier_transform_profile_mapping as _normalize_supplier_transform_profile_mapping,
    normalize_supplier_transform_profile_options as _normalize_supplier_transform_profile_options,
    ordered_supplier_transform_profile_composite_fields as _ordered_supplier_transform_profile_composite_fields,
    ordered_supplier_transform_profile_mapping as _ordered_supplier_transform_profile_mapping,
)
from ..persistence import profile_store as _profile_store
from ..runtime_paths import supplier_transform_profiles_path as _supplier_transform_profiles_path


def persist_supplier_transform_profile(
    session_state: dict[str, object],
    *,
    supplier_name: str,
    target_to_source: dict[str, str],
    composite_fields: Optional[dict[str, list[str]]] = None,
    filters: Optional[dict[str, object]] = None,
    options: dict[str, bool],
) -> Optional[str]:
    normalized_supplier_name = str(supplier_name).strip()
    if normalized_supplier_name == "":
        return "Kan inte spara profil utan leverantörsnamn."

    profiles: dict[str, dict[str, object]] = {}
    for name, raw_profile in session_state.get("supplier_transform_profiles", {}).items():
        if not isinstance(name, str) or not isinstance(raw_profile, dict):
            continue
        mapping, normalized_composite_fields, normalized_filters, normalized_options = (
            _normalize_supplier_transform_profile_details(raw_profile)
        )
        if not mapping:
            continue
        normalized_profile: dict[str, object] = {
            "target_to_source": _ordered_supplier_transform_profile_mapping(mapping),
            "options": normalized_options,
        }
        if normalized_composite_fields:
            normalized_profile["composite_fields"] = _ordered_supplier_transform_profile_composite_fields(
                normalized_composite_fields
            )
        normalized_profile_filters = _normalize_supplier_transform_profile_filters(
            normalized_filters
        )
        if normalized_profile_filters != dict(SUPPLIER_TRANSFORM_DEFAULT_FILTERS):
            normalized_profile["filters"] = normalized_profile_filters
        profiles[name] = normalized_profile

    profile_payload: dict[str, object] = {
        "target_to_source": _ordered_supplier_transform_profile_mapping(
            _normalize_supplier_transform_profile_mapping(target_to_source)
        ),
        "options": _normalize_supplier_transform_profile_options(options),
    }
    normalized_composite_fields = _ordered_supplier_transform_profile_composite_fields(
        composite_fields if isinstance(composite_fields, dict) else {}
    )
    if normalized_composite_fields:
        profile_payload["composite_fields"] = normalized_composite_fields
    normalized_filters = _normalize_supplier_transform_profile_filters(
        filters if isinstance(filters, dict) else {}
    )
    if normalized_filters != dict(SUPPLIER_TRANSFORM_DEFAULT_FILTERS):
        profile_payload["filters"] = normalized_filters
    profiles[normalized_supplier_name] = profile_payload

    save_error = _profile_store.save_profiles(
        _supplier_transform_profiles_path(),
        profiles=profiles,
    )
    session_state["supplier_transform_profiles_save_error"] = save_error
    if save_error is None:
        session_state["supplier_transform_profiles"] = profiles
        session_state["supplier_transform_profiles_load_error"] = None
    return save_error


def delete_supplier_transform_profile(
    session_state: dict[str, object],
    *,
    supplier_name: str,
) -> Optional[str]:
    normalized_supplier_name = str(supplier_name).strip()
    if normalized_supplier_name == "":
        return "Kan inte ta bort profil utan leverantörsnamn."

    profiles: dict[str, dict[str, object]] = {}
    for name, raw_profile in session_state.get("supplier_transform_profiles", {}).items():
        if not isinstance(name, str) or not isinstance(raw_profile, dict):
            continue
        if name.strip().casefold() == normalized_supplier_name.casefold():
            continue
        mapping, normalized_composite_fields, normalized_filters, normalized_options = (
            _normalize_supplier_transform_profile_details(raw_profile)
        )
        if not mapping:
            continue
        normalized_profile: dict[str, object] = {
            "target_to_source": _ordered_supplier_transform_profile_mapping(mapping),
            "options": normalized_options,
        }
        if normalized_composite_fields:
            normalized_profile["composite_fields"] = _ordered_supplier_transform_profile_composite_fields(
                normalized_composite_fields
            )
        normalized_profile_filters = _normalize_supplier_transform_profile_filters(
            normalized_filters
        )
        if normalized_profile_filters != dict(SUPPLIER_TRANSFORM_DEFAULT_FILTERS):
            normalized_profile["filters"] = normalized_profile_filters
        profiles[name] = normalized_profile

    save_error = _profile_store.save_profiles(
        _supplier_transform_profiles_path(),
        profiles=profiles,
    )
    session_state["supplier_transform_profiles_save_error"] = save_error
    if save_error is None:
        session_state["supplier_transform_profiles"] = profiles
        session_state["supplier_transform_profiles_load_error"] = None
    return save_error

