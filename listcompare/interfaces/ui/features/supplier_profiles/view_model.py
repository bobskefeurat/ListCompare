from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from listcompare.core.suppliers.profile import (
    SUPPLIER_HICORE_RENAME_COLUMNS,
    SUPPLIER_HICORE_SUPPLIER_COLUMN,
    SUPPLIER_TRANSFORM_DEFAULT_FILTERS,
    SUPPLIER_TRANSFORM_DEFAULT_OPTIONS,
    SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN,
    SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES,
    find_duplicate_names as _find_duplicate_names,
    normalize_supplier_transform_profile_details as _normalize_supplier_transform_profile_details,
)


@dataclass(frozen=True)
class UiMessage:
    level: str
    text: str


@dataclass(frozen=True)
class SupplierProfileState:
    mapping: dict[str, str]
    composite_fields: dict[str, list[str]]
    filters: dict[str, object]
    options: dict[str, bool]
    has_saved_profile: bool


@dataclass(frozen=True)
class SupplierSourcePreviewState:
    source_columns: list[str]
    duplicate_source_columns: list[str]
    preview_row_count: int
    preview_df: pd.DataFrame


def supplier_file_unique_values(df_supplier: pd.DataFrame, *, column_name: str) -> list[str]:
    if column_name not in df_supplier.columns:
        return []

    unique_by_folded: dict[str, str] = {}
    for raw_value in df_supplier[column_name].tolist():
        if pd.isna(raw_value):
            continue
        value = str(raw_value).strip()
        if value == "" or value.casefold() == "nan":
            continue
        folded = value.casefold()
        if folded not in unique_by_folded:
            unique_by_folded[folded] = value
    return sorted(unique_by_folded.values(), key=lambda item: item.casefold())


def selected_supplier_profile_state(
    *,
    selected_supplier_name: str,
    supplier_transform_profiles_raw: object,
) -> SupplierProfileState:
    supplier_transform_profiles = (
        supplier_transform_profiles_raw if isinstance(supplier_transform_profiles_raw, dict) else {}
    )
    mapping: dict[str, str] = {}
    composite_fields: dict[str, list[str]] = {}
    filters = dict(SUPPLIER_TRANSFORM_DEFAULT_FILTERS)
    options = dict(SUPPLIER_TRANSFORM_DEFAULT_OPTIONS)
    if selected_supplier_name != "":
        raw_profile = supplier_transform_profiles.get(selected_supplier_name, {})
        if isinstance(raw_profile, dict):
            mapping, composite_fields, filters, options = _normalize_supplier_transform_profile_details(
                raw_profile
            )
    return SupplierProfileState(
        mapping=mapping,
        composite_fields=composite_fields,
        filters=filters,
        options=options,
        has_saved_profile=bool(mapping),
    )


def supplier_profile_summary_rows(
    *,
    selected_supplier_name: str,
    profile_mapping: dict[str, str],
    profile_composite_fields: dict[str, list[str]],
) -> list[dict[str, str]]:
    rows = [
        {
            "HiCore-kolumn": target_column,
            "Leverantörskolumn": (
                " + ".join(profile_composite_fields[target_column])
                if target_column in profile_composite_fields
                else profile_mapping.get(target_column, "(ej mappad)")
            ),
        }
        for target_column in SUPPLIER_HICORE_RENAME_COLUMNS
    ]
    rows.append(
        {
            "HiCore-kolumn": SUPPLIER_HICORE_SUPPLIER_COLUMN,
            "Leverantörskolumn": f"Värde från supplier_index: {selected_supplier_name}",
        }
    )
    return rows


def supplier_profile_filter_summary(profile_filters: dict[str, object]) -> Optional[str]:
    saved_brand_source = str(
        profile_filters.get(SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN, "")
    ).strip()
    saved_excluded_brands = [
        str(value)
        for value in profile_filters.get(
            SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES,
            [],
        )
    ]
    if saved_brand_source == "" and not saved_excluded_brands:
        return None
    return (
        "Varumärkesfilter: "
        f"brand-kolumn = {saved_brand_source or '(ingen vald)'}, "
        f"exkluderade värden = {', '.join(saved_excluded_brands) if saved_excluded_brands else '(inga)' }."
    )


def supplier_source_preview_state(df_supplier: pd.DataFrame) -> SupplierSourcePreviewState:
    source_columns = [str(column).strip() for column in df_supplier.columns]
    preview_df = df_supplier.copy()
    preview_df.columns = source_columns
    return SupplierSourcePreviewState(
        source_columns=source_columns,
        duplicate_source_columns=_find_duplicate_names(source_columns),
        preview_row_count=min(len(df_supplier), 10),
        preview_df=preview_df,
    )


def supplier_file_prompt_message(*, selected_supplier_name: str) -> UiMessage:
    if selected_supplier_name == "":
        return UiMessage(
            level="info",
            text="Välj leverantör och ladda upp en leverantörsfil för att mappa kolumner.",
        )
    return UiMessage(
        level="info",
        text=(
            "Ladda upp en leverantörsfil för att mappa kolumner för vald leverantör. "
            "Uppladdning är obligatorisk för att skapa eller uppdatera profil."
        ),
    )


def supplier_profile_file_messages(
    *,
    selected_supplier_name: str,
    saved_profile: dict[str, str],
    saved_composite_fields: dict[str, list[str]],
    source_columns: list[str],
    saved_brand_source: str,
    saved_excluded_brands: list[str],
    current_brand_values: list[str],
) -> list[UiMessage]:
    if selected_supplier_name == "":
        return [
            UiMessage(
                level="info",
                text="Välj leverantör för att kunna ladda eller spara en profil.",
            )
        ]
    if not saved_profile:
        return [
            UiMessage(
                level="info",
                text=(
                    f'Ingen sparad profil finns för "{selected_supplier_name}". '
                    "Matcha kolumnerna och spara en profil."
                ),
            )
        ]

    valid_saved_targets = [
        target
        for target, source in saved_profile.items()
        if target in SUPPLIER_HICORE_RENAME_COLUMNS and source in source_columns
    ]
    valid_saved_targets.extend(
        [
            target
            for target, source_list in saved_composite_fields.items()
            if target in SUPPLIER_HICORE_RENAME_COLUMNS
            and all(source in source_columns for source in source_list)
        ]
    )

    missing_saved_targets = [
        target
        for target, source in saved_profile.items()
        if target in SUPPLIER_HICORE_RENAME_COLUMNS and source not in source_columns
    ]
    missing_saved_targets.extend(
        [
            target
            for target, source_list in saved_composite_fields.items()
            if target in SUPPLIER_HICORE_RENAME_COLUMNS
            and any(source not in source_columns for source in source_list)
        ]
    )

    messages: list[UiMessage] = []
    if valid_saved_targets:
        messages.append(
            UiMessage(
                level="success",
                text=(
                    f'Sparad profil hittad för "{selected_supplier_name}". '
                    f"Förifyller {len(set(valid_saved_targets))} kolumnval."
                ),
            )
        )
    if missing_saved_targets:
        messages.append(
            UiMessage(
                level="warning",
                text=(
                    "Den sparade profilen matchar inte fullt ut mot aktuell fil. "
                    "Välj om följande HiCore-kolumner: "
                    + ", ".join(sorted(set(missing_saved_targets), key=lambda item: item.casefold()))
                ),
            )
        )

    if saved_brand_source != "" and saved_brand_source not in source_columns:
        messages.append(
            UiMessage(
                level="warning",
                text=(
                    "Den sparade profilens brand-kolumn finns inte i aktuell fil: "
                    + saved_brand_source
                ),
            )
        )
        return messages

    if saved_excluded_brands and saved_brand_source != "":
        current_brand_values_folded = {value.casefold() for value in current_brand_values}
        missing_saved_excluded = [
            brand_name
            for brand_name in saved_excluded_brands
            if brand_name.casefold() not in current_brand_values_folded
        ]
        if missing_saved_excluded:
            messages.append(
                UiMessage(
                    level="warning",
                    text=(
                        "Den sparade profilen innehåller exkluderade varumärken som inte finns i aktuell fil: "
                        + ", ".join(missing_saved_excluded)
                    ),
                )
            )
    return messages


def filter_supplier_names(names: list[str], query: str) -> list[str]:
    normalized_query = str(query).strip().casefold()
    if normalized_query == "":
        return list(names)
    return [name for name in names if normalized_query in str(name).casefold()]


def selected_dataframe_row_index(selection_event: object) -> Optional[int]:
    selection = getattr(selection_event, "selection", None)
    if selection is None:
        return None

    selected_rows = getattr(selection, "rows", None)
    if isinstance(selected_rows, (list, tuple)) and selected_rows:
        try:
            return int(selected_rows[0])
        except Exception:
            pass

    selected_cells = getattr(selection, "cells", None)
    if isinstance(selected_cells, (list, tuple)) and selected_cells:
        first_cell = selected_cells[0]
        if isinstance(first_cell, dict):
            row_value = first_cell.get("row")
            try:
                return int(row_value)
            except Exception:
                return None
        if isinstance(first_cell, (list, tuple)) and first_cell:
            try:
                return int(first_cell[0])
            except Exception:
                return None
    return None
