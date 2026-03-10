from __future__ import annotations

from .constants import (
    SUPPLIER_TRANSFORM_DEFAULT_FILTERS,
    SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN,
    SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES,
)
from .normalize import (
    _normalize_profile_text,
    normalize_supplier_transform_profile_details,
    normalize_supplier_transform_profile_filters,
    ordered_supplier_transform_profile_composite_fields,
    ordered_supplier_transform_profile_mapping,
)


def normalized_profiles_dict(
    raw_profiles: dict[object, object],
) -> dict[str, dict[str, object]]:
    profiles: dict[str, dict[str, object]] = {}
    for raw_supplier_name, raw_profile in raw_profiles.items():
        supplier_name = _normalize_profile_text(raw_supplier_name)
        if supplier_name == "":
            continue
        if not isinstance(raw_profile, dict):
            continue

        mapping, composite_fields, filters, options = normalize_supplier_transform_profile_details(
            raw_profile
        )
        if not mapping:
            continue

        normalized_profile: dict[str, object] = {
            "target_to_source": ordered_supplier_transform_profile_mapping(mapping),
            "options": options,
        }
        if composite_fields:
            normalized_profile["composite_fields"] = ordered_supplier_transform_profile_composite_fields(
                composite_fields
            )
        normalized_filters = normalize_supplier_transform_profile_filters(filters)
        if normalized_filters != dict(SUPPLIER_TRANSFORM_DEFAULT_FILTERS):
            normalized_profile["filters"] = normalized_filters
        profiles[supplier_name] = normalized_profile
    return profiles


def parse_profiles_payload(raw_payload: object) -> dict[str, dict[str, object]]:
    if not isinstance(raw_payload, dict):
        raise ValueError("supplier_transform_profiles.json måste innehålla ett JSON-objekt.")
    raw_profiles = raw_payload.get("profiles", raw_payload)
    if not isinstance(raw_profiles, dict):
        raise ValueError('Fältet "profiles" måste vara ett JSON-objekt.')
    return normalized_profiles_dict(raw_profiles)


def build_profiles_payload(
    profiles: dict[str, dict[str, object]],
) -> dict[str, dict[str, dict[str, object]]]:
    return {"profiles": normalized_profiles_dict(profiles)}


def profile_filters_payload(filters: dict[str, object]) -> dict[str, object]:
    normalized_filters = normalize_supplier_transform_profile_filters(filters)
    if normalized_filters == dict(SUPPLIER_TRANSFORM_DEFAULT_FILTERS):
        return {}
    return {
        SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN: str(
            normalized_filters[SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN]
        ).strip(),
        SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES: [
            str(value)
            for value in normalized_filters[SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES]
        ],
    }
