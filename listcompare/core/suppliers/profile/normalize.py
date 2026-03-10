from __future__ import annotations

from .constants import (
    SUPPLIER_HICORE_RENAME_COLUMNS,
    SUPPLIER_TRANSFORM_COMPOSITE_SUPPORTED_TARGETS,
    SUPPLIER_TRANSFORM_DEFAULT_FILTERS,
    SUPPLIER_TRANSFORM_DEFAULT_OPTIONS,
    SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN,
    SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES,
)


def _normalize_profile_text(raw_value: object) -> str:
    value = str(raw_value).strip()
    if value == "" or value.casefold() == "nan":
        return ""
    return value


def _normalize_unique_profile_texts(raw_values: object) -> list[str]:
    if not isinstance(raw_values, (list, tuple)):
        return []

    unique_by_folded: dict[str, str] = {}
    ordered: list[str] = []
    for raw_value in raw_values:
        value = _normalize_profile_text(raw_value)
        if value == "":
            continue
        folded = value.casefold()
        if folded in unique_by_folded:
            continue
        unique_by_folded[folded] = value
        ordered.append(value)
    return ordered


def normalize_supplier_transform_profile_mapping(raw_mapping: dict[object, object]) -> dict[str, str]:
    normalized_mapping: dict[str, str] = {}
    for target_column in SUPPLIER_HICORE_RENAME_COLUMNS:
        if target_column not in raw_mapping:
            continue
        source_column = _normalize_profile_text(raw_mapping[target_column])
        if source_column == "":
            continue
        normalized_mapping[target_column] = source_column
    return normalized_mapping


def normalize_supplier_transform_profile_composite_fields(
    raw_composite_fields: dict[object, object],
) -> dict[str, list[str]]:
    normalized_composite_fields: dict[str, list[str]] = {}
    for target_column in SUPPLIER_TRANSFORM_COMPOSITE_SUPPORTED_TARGETS:
        raw_sources = raw_composite_fields.get(target_column, [])
        normalized_sources = _normalize_unique_profile_texts(raw_sources)
        if normalized_sources:
            normalized_composite_fields[target_column] = normalized_sources
    return normalized_composite_fields


def normalize_supplier_transform_profile_filters(
    raw_filters: dict[object, object],
) -> dict[str, object]:
    normalized_filters = dict(SUPPLIER_TRANSFORM_DEFAULT_FILTERS)
    normalized_filters[SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN] = _normalize_profile_text(
        raw_filters.get(SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN, "")
    )
    normalized_filters[SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES] = (
        _normalize_unique_profile_texts(
            raw_filters.get(SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES, [])
        )
    )
    return normalized_filters


def normalize_supplier_transform_profile_options(raw_options: dict[object, object]) -> dict[str, bool]:
    normalized_options = dict(SUPPLIER_TRANSFORM_DEFAULT_OPTIONS)
    for option_name, default_value in SUPPLIER_TRANSFORM_DEFAULT_OPTIONS.items():
        raw_value = raw_options.get(option_name, default_value)
        if isinstance(raw_value, bool):
            normalized_options[option_name] = raw_value
            continue
        if isinstance(raw_value, (int, float)):
            normalized_options[option_name] = bool(raw_value)
            continue
        if isinstance(raw_value, str):
            folded = raw_value.strip().casefold()
            if folded in ("1", "true", "yes", "ja", "on"):
                normalized_options[option_name] = True
            elif folded in ("0", "false", "no", "nej", "off", ""):
                normalized_options[option_name] = False
    return normalized_options


def normalize_supplier_transform_profile_details(
    raw_profile: dict[object, object],
) -> tuple[dict[str, str], dict[str, list[str]], dict[str, object], dict[str, bool]]:
    profile_mapping_raw = raw_profile.get("target_to_source", raw_profile)
    mapping = (
        normalize_supplier_transform_profile_mapping(profile_mapping_raw)
        if isinstance(profile_mapping_raw, dict)
        else {}
    )

    raw_composite_fields = raw_profile.get("composite_fields", {})
    composite_fields = (
        normalize_supplier_transform_profile_composite_fields(raw_composite_fields)
        if isinstance(raw_composite_fields, dict)
        else {}
    )
    for target_column in composite_fields:
        mapping.pop(target_column, None)

    raw_filters = raw_profile.get("filters", {})
    filters = (
        normalize_supplier_transform_profile_filters(raw_filters)
        if isinstance(raw_filters, dict)
        else dict(SUPPLIER_TRANSFORM_DEFAULT_FILTERS)
    )

    raw_options = raw_profile.get("options", {})
    options = (
        normalize_supplier_transform_profile_options(raw_options)
        if isinstance(raw_options, dict)
        else dict(SUPPLIER_TRANSFORM_DEFAULT_OPTIONS)
    )
    return mapping, composite_fields, filters, options


def normalize_supplier_transform_profile(
    raw_profile: dict[object, object],
) -> tuple[dict[str, str], dict[str, bool]]:
    mapping, _composite_fields, _filters, options = normalize_supplier_transform_profile_details(
        raw_profile
    )
    return mapping, options


def ordered_supplier_transform_profile_mapping(mapping: dict[str, str]) -> dict[str, str]:
    return {
        target: mapping[target]
        for target in SUPPLIER_HICORE_RENAME_COLUMNS
        if target in mapping
    }


def ordered_supplier_transform_profile_composite_fields(
    composite_fields: dict[str, list[str]],
) -> dict[str, list[str]]:
    return {
        target: list(composite_fields[target])
        for target in SUPPLIER_TRANSFORM_COMPOSITE_SUPPORTED_TARGETS
        if target in composite_fields and composite_fields[target]
    }
