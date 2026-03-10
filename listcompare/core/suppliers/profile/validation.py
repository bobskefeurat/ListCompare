from __future__ import annotations

from typing import Optional

from .constants import (
    SUPPLIER_HICORE_RENAME_COLUMNS,
    SUPPLIER_HICORE_SKU_COLUMN,
    SUPPLIER_HICORE_SUPPLIER_COLUMN,
    SUPPLIER_TRANSFORM_COMPOSITE_SUPPORTED_TARGETS,
    SUPPLIER_TRANSFORM_DEFAULT_FILTERS,
    SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN,
    SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES,
)
from .normalize import normalize_supplier_transform_profile_filters


def profile_has_required_sku_mapping(mapping: dict[str, str]) -> bool:
    return str(mapping.get(SUPPLIER_HICORE_SKU_COLUMN, "")).strip() != ""


def _profile_required_source_columns(
    mapping: dict[str, str],
    *,
    composite_fields: Optional[dict[str, list[str]]] = None,
    filters: Optional[dict[str, object]] = None,
) -> set[str]:
    required_sources = {
        str(source).strip()
        for source in mapping.values()
        if str(source).strip() != ""
    }
    normalized_composite_fields = composite_fields if isinstance(composite_fields, dict) else {}
    for source_columns in normalized_composite_fields.values():
        for source_column in source_columns:
            source = str(source_column).strip()
            if source != "":
                required_sources.add(source)

    normalized_filters = (
        normalize_supplier_transform_profile_filters(filters)
        if isinstance(filters, dict)
        else dict(SUPPLIER_TRANSFORM_DEFAULT_FILTERS)
    )
    excluded_brand_values = normalized_filters[SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES]
    brand_source_column = str(
        normalized_filters[SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN]
    ).strip()
    if brand_source_column != "" and excluded_brand_values:
        required_sources.add(brand_source_column)

    return required_sources


def missing_profile_source_columns(
    mapping: dict[str, str],
    source_columns: list[str],
    *,
    composite_fields: Optional[dict[str, list[str]]] = None,
    filters: Optional[dict[str, object]] = None,
) -> list[str]:
    available_columns = {str(column).strip() for column in source_columns}
    missing = {
        source
        for source in _profile_required_source_columns(
            mapping,
            composite_fields=composite_fields,
            filters=filters,
        )
        if source not in available_columns
    }
    return sorted(missing, key=lambda item: item.casefold())


def matches_profile_output_format(
    mapping: dict[str, str],
    source_columns: list[str],
    *,
    composite_fields: Optional[dict[str, list[str]]] = None,
) -> bool:
    available_columns = {str(column).strip() for column in source_columns}
    required_targets = {
        target for target in SUPPLIER_HICORE_RENAME_COLUMNS if str(mapping.get(target, "")).strip() != ""
    }
    normalized_composite_fields = composite_fields if isinstance(composite_fields, dict) else {}
    required_targets.update(
        {
            target
            for target, source_columns_for_target in normalized_composite_fields.items()
            if target in SUPPLIER_TRANSFORM_COMPOSITE_SUPPORTED_TARGETS and source_columns_for_target
        }
    )
    if not required_targets:
        return False
    has_all_targets = all(target in available_columns for target in required_targets)
    has_supplier_column = SUPPLIER_HICORE_SUPPLIER_COLUMN in available_columns
    return has_all_targets and has_supplier_column
