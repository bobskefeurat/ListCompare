from __future__ import annotations

from ....core.suppliers.profile import (
    SUPPLIER_TRANSFORM_DEFAULT_FILTERS,
    SUPPLIER_TRANSFORM_DEFAULT_OPTIONS,
    normalize_supplier_transform_profile_details as _normalize_supplier_transform_profile_details,
)


def get_supplier_transform_profile(
    session_state: dict[str, object],
    supplier_name: str,
) -> tuple[dict[str, str], dict[str, bool]]:
    mapping, _composite_fields, _filters, options = get_supplier_transform_profile_details(
        session_state,
        supplier_name,
    )
    return mapping, options


def get_supplier_transform_profile_details(
    session_state: dict[str, object],
    supplier_name: str,
) -> tuple[dict[str, str], dict[str, list[str]], dict[str, object], dict[str, bool]]:
    normalized_supplier_name = str(supplier_name).strip()
    if normalized_supplier_name == "":
        return (
            {},
            {},
            dict(SUPPLIER_TRANSFORM_DEFAULT_FILTERS),
            dict(SUPPLIER_TRANSFORM_DEFAULT_OPTIONS),
        )

    raw_profiles = session_state.get("supplier_transform_profiles", {})
    if not isinstance(raw_profiles, dict):
        return (
            {},
            {},
            dict(SUPPLIER_TRANSFORM_DEFAULT_FILTERS),
            dict(SUPPLIER_TRANSFORM_DEFAULT_OPTIONS),
        )
    raw_profile = raw_profiles.get(normalized_supplier_name, {})
    if not isinstance(raw_profile, dict):
        return (
            {},
            {},
            dict(SUPPLIER_TRANSFORM_DEFAULT_FILTERS),
            dict(SUPPLIER_TRANSFORM_DEFAULT_OPTIONS),
        )
    return _normalize_supplier_transform_profile_details(raw_profile)


def supplier_has_saved_profile(session_state: dict[str, object], supplier_name: str) -> bool:
    mapping, _ = get_supplier_transform_profile(session_state, supplier_name)
    return bool(mapping)


def split_suppliers_by_profile(
    session_state: dict[str, object],
    supplier_options: list[str],
) -> tuple[list[str], list[str]]:
    suppliers_with_profile: list[str] = []
    suppliers_without_profile: list[str] = []
    for supplier_name in supplier_options:
        if supplier_has_saved_profile(session_state, supplier_name):
            suppliers_with_profile.append(supplier_name)
        else:
            suppliers_without_profile.append(supplier_name)
    return suppliers_with_profile, suppliers_without_profile
