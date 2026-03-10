from __future__ import annotations

from typing import Optional

import pandas as pd

from .constants import (
    SUPPLIER_HICORE_RENAME_COLUMNS,
    SUPPLIER_HICORE_SKU_COLUMN,
    SUPPLIER_HICORE_SUPPLIER_COLUMN,
    SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN,
    SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES,
)
from .normalize import (
    _normalize_profile_text,
    normalize_supplier_transform_profile_composite_fields,
    normalize_supplier_transform_profile_filters,
)
from .validation import _profile_required_source_columns


def find_duplicate_names(values: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    duplicates: list[str] = []
    for value in values:
        counts[value] = counts.get(value, 0) + 1
        if counts[value] == 2:
            duplicates.append(value)
    return sorted(duplicates, key=lambda item: item.casefold())


def normalize_supplier_transform_sku_value(
    raw_value: object,
    *,
    strip_leading_zeros: bool,
) -> str:
    if pd.isna(raw_value):
        return ""
    value = str(raw_value).strip()
    if value == "" or value.casefold() == "nan":
        return ""
    if strip_leading_zeros:
        value = value.lstrip("0")
        if value == "":
            return "0"
    return value


def _supplier_transform_cell_text(raw_value: object) -> str:
    if pd.isna(raw_value):
        return ""
    return _normalize_profile_text(raw_value)


def _build_composite_supplier_value(row: pd.Series, *, source_columns: list[str]) -> str:
    parts = [
        _supplier_transform_cell_text(row.get(source_column, ""))
        for source_column in source_columns
    ]
    return " ".join(part for part in parts if part != "")


def build_supplier_hicore_renamed_copy(
    df_supplier: pd.DataFrame,
    *,
    target_to_source: dict[str, str],
    supplier_name: str,
    composite_fields: Optional[dict[str, list[str]]] = None,
    brand_source_column: str = "",
    excluded_brand_values: Optional[list[str]] = None,
    strip_leading_zeros_from_sku: bool = False,
    ignore_rows_missing_sku: bool = False,
    source_row_column: str = "",
) -> pd.DataFrame:
    normalized_target_to_source = {
        str(target).strip(): str(source).strip()
        for target, source in target_to_source.items()
        if str(target).strip() in SUPPLIER_HICORE_RENAME_COLUMNS and str(source).strip() != ""
    }
    normalized_composite_fields = (
        normalize_supplier_transform_profile_composite_fields(composite_fields)
        if isinstance(composite_fields, dict)
        else {}
    )
    for target_column in normalized_composite_fields:
        normalized_target_to_source.pop(target_column, None)
    if not normalized_target_to_source and not normalized_composite_fields:
        raise ValueError(
            "Matcha minst en HiCore-kolumn eller bygg ett sammansatt artikelnamn innan export."
        )

    normalized_supplier_name = _normalize_profile_text(supplier_name)
    if normalized_supplier_name == "":
        raise ValueError("Välj leverantör från leverantörslistan innan export.")

    normalized_filters = normalize_supplier_transform_profile_filters(
        {
            SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN: brand_source_column,
            SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES: excluded_brand_values or [],
        }
    )

    prepared_df = df_supplier.copy()
    prepared_df.columns = [str(col).strip() for col in prepared_df.columns]

    available_columns = {str(col).strip() for col in prepared_df.columns}
    required_sources = sorted(
        _profile_required_source_columns(
            normalized_target_to_source,
            composite_fields=normalized_composite_fields,
            filters=normalized_filters,
        ),
        key=lambda item: item.casefold(),
    )
    missing_sources = [source for source in required_sources if source not in available_columns]
    if missing_sources:
        raise ValueError(
            "Vald(e) kolumn(er) finns inte i leverantörsfilen: " + ", ".join(missing_sources)
        )

    configured_brand_source = str(
        normalized_filters[SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN]
    ).strip()
    excluded_brand_values_folded = {
        str(value).strip().casefold()
        for value in normalized_filters[SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES]
        if str(value).strip() != ""
    }
    if configured_brand_source != "" and excluded_brand_values_folded:
        brand_matches = prepared_df[configured_brand_source].map(
            lambda raw_value: _supplier_transform_cell_text(raw_value).casefold()
            in excluded_brand_values_folded
        )
        prepared_df = prepared_df.loc[~brand_matches].copy()

    sku_source_column = normalized_target_to_source.get(SUPPLIER_HICORE_SKU_COLUMN)
    if sku_source_column is not None:
        normalized_sku_values = prepared_df[sku_source_column].map(
            lambda raw_value: normalize_supplier_transform_sku_value(
                raw_value,
                strip_leading_zeros=strip_leading_zeros_from_sku,
            )
        )
        prepared_df.loc[:, sku_source_column] = normalized_sku_values
        if ignore_rows_missing_sku:
            prepared_df = prepared_df.loc[normalized_sku_values != ""].copy()

    renamed_df = pd.DataFrame(index=prepared_df.index)
    ordered_targets: list[str] = []
    for target_column in SUPPLIER_HICORE_RENAME_COLUMNS:
        if target_column in normalized_composite_fields:
            renamed_df[target_column] = prepared_df.apply(
                lambda row: _build_composite_supplier_value(
                    row,
                    source_columns=normalized_composite_fields[target_column],
                ),
                axis=1,
            )
            ordered_targets.append(target_column)
            continue

        source_column = normalized_target_to_source.get(target_column)
        if source_column is None:
            continue
        renamed_df[target_column] = prepared_df[source_column]
        ordered_targets.append(target_column)

    renamed_df[SUPPLIER_HICORE_SUPPLIER_COLUMN] = normalized_supplier_name
    ordered_output_columns = [*ordered_targets, SUPPLIER_HICORE_SUPPLIER_COLUMN]

    normalized_source_row_column = str(source_row_column).strip()
    if normalized_source_row_column != "":
        renamed_df[normalized_source_row_column] = prepared_df.index.map(
            lambda raw_index: int(raw_index) + 2
        )
        ordered_output_columns.append(normalized_source_row_column)

    renamed_df = renamed_df.loc[:, ordered_output_columns]
    return renamed_df.reset_index(drop=True)
