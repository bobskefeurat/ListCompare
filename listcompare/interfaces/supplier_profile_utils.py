from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

SUPPLIER_HICORE_RENAME_COLUMNS = (
    "Art.märkning",
    "Artikelnamn",
    "Varumärke",
    "Inköpspris",
    "UtprisInklMoms",
    "Lev.artnr",
)
SUPPLIER_HICORE_SUPPLIER_COLUMN = "Leverantör"
SUPPLIER_HICORE_SKU_COLUMN = "Art.märkning"
SUPPLIER_HICORE_NAME_COLUMN = "Artikelnamn"

SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS = "strip_leading_zeros_from_sku"
SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU = "ignore_rows_missing_sku"
SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN = "brand_source_column"
SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES = "excluded_brand_values"
SUPPLIER_TRANSFORM_DEFAULT_OPTIONS: dict[str, bool] = {
    SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS: False,
    SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU: False,
}
SUPPLIER_TRANSFORM_DEFAULT_FILTERS: dict[str, object] = {
    SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN: "",
    SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES: [],
}
SUPPLIER_TRANSFORM_COMPOSITE_SUPPORTED_TARGETS = (
    SUPPLIER_HICORE_NAME_COLUMN,
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


def safe_filename_part(value: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    cleaned = "".join("_" if ch in invalid_chars else ch for ch in str(value).strip())
    cleaned = "_".join(part for part in cleaned.split())
    return cleaned if cleaned != "" else "leverantor"


def rebuilt_supplier_file_name(supplier_name: str, *, extension: str = ".xlsx") -> str:
    safe_supplier = safe_filename_part(supplier_name)
    normalized_extension = str(extension).strip()
    if normalized_extension == "":
        normalized_extension = ".xlsx"
    if not normalized_extension.startswith("."):
        normalized_extension = f".{normalized_extension}"
    return f"{safe_supplier}_prislista_{date.today().isoformat()}{normalized_extension}"


def load_supplier_transform_profiles(path: Path) -> tuple[dict[str, dict[str, object]], Optional[str]]:
    if not path.exists():
        return {}, None

    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, dict):
            raise ValueError("supplier_transform_profiles.json måste innehålla ett JSON-objekt.")

        raw_profiles = raw.get("profiles", raw)
        if not isinstance(raw_profiles, dict):
            raise ValueError('Fältet "profiles" måste vara ett JSON-objekt.')

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
            if mapping:
                normalized_profile: dict[str, object] = {
                    "target_to_source": ordered_supplier_transform_profile_mapping(mapping),
                    "options": options,
                }
                if composite_fields:
                    normalized_profile["composite_fields"] = (
                        ordered_supplier_transform_profile_composite_fields(composite_fields)
                    )
                normalized_filters = normalize_supplier_transform_profile_filters(filters)
                if (
                    str(
                        normalized_filters[SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN]
                    ).strip()
                    != ""
                    or normalized_filters[SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES]
                ):
                    normalized_profile["filters"] = normalized_filters
                profiles[supplier_name] = normalized_profile

        return profiles, None
    except Exception as exc:
        return {}, str(exc)


def save_supplier_transform_profiles(
    path: Path,
    *,
    profiles: dict[str, dict[str, object]],
) -> Optional[str]:
    payload_profiles: dict[str, dict[str, object]] = {}
    for raw_supplier_name, raw_profile in profiles.items():
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
        payload_profile: dict[str, object] = {
            "target_to_source": ordered_supplier_transform_profile_mapping(mapping),
            "options": options,
        }
        if composite_fields:
            payload_profile["composite_fields"] = ordered_supplier_transform_profile_composite_fields(
                composite_fields
            )
        normalized_filters = normalize_supplier_transform_profile_filters(filters)
        if (
            str(normalized_filters[SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN]).strip() != ""
            or normalized_filters[SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES]
        ):
            payload_profile["filters"] = normalized_filters
        payload_profiles[supplier_name] = payload_profile

    payload = {"profiles": payload_profiles}
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return None
    except Exception as exc:
        return str(exc)


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
