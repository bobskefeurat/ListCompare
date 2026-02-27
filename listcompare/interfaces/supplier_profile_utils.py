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

SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS = "strip_leading_zeros_from_sku"
SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU = "ignore_rows_missing_sku"
SUPPLIER_TRANSFORM_DEFAULT_OPTIONS: dict[str, bool] = {
    SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS: False,
    SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU: False,
}


def normalize_supplier_transform_profile_mapping(raw_mapping: dict[object, object]) -> dict[str, str]:
    normalized_mapping: dict[str, str] = {}
    for target_column in SUPPLIER_HICORE_RENAME_COLUMNS:
        if target_column not in raw_mapping:
            continue
        source_column = str(raw_mapping[target_column]).strip()
        if source_column == "":
            continue
        normalized_mapping[target_column] = source_column
    return normalized_mapping


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


def normalize_supplier_transform_profile(
    raw_profile: dict[object, object],
) -> tuple[dict[str, str], dict[str, bool]]:
    profile_mapping_raw = raw_profile.get("target_to_source", raw_profile)
    mapping = (
        normalize_supplier_transform_profile_mapping(profile_mapping_raw)
        if isinstance(profile_mapping_raw, dict)
        else {}
    )
    raw_options = raw_profile.get("options", {})
    options = (
        normalize_supplier_transform_profile_options(raw_options)
        if isinstance(raw_options, dict)
        else dict(SUPPLIER_TRANSFORM_DEFAULT_OPTIONS)
    )
    return mapping, options


def ordered_supplier_transform_profile_mapping(mapping: dict[str, str]) -> dict[str, str]:
    return {
        target: mapping[target]
        for target in SUPPLIER_HICORE_RENAME_COLUMNS
        if target in mapping
    }


def profile_has_required_sku_mapping(mapping: dict[str, str]) -> bool:
    return str(mapping.get(SUPPLIER_HICORE_SKU_COLUMN, "")).strip() != ""


def missing_profile_source_columns(mapping: dict[str, str], source_columns: list[str]) -> list[str]:
    available_columns = {str(column).strip() for column in source_columns}
    missing = {
        str(source).strip()
        for source in mapping.values()
        if str(source).strip() not in available_columns
    }
    return sorted(missing, key=lambda item: item.casefold())


def matches_profile_output_format(mapping: dict[str, str], source_columns: list[str]) -> bool:
    available_columns = {str(column).strip() for column in source_columns}
    required_targets = [
        target for target in SUPPLIER_HICORE_RENAME_COLUMNS if str(mapping.get(target, "")).strip() != ""
    ]
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
            supplier_name = str(raw_supplier_name).strip()
            if supplier_name == "":
                continue
            if not isinstance(raw_profile, dict):
                continue

            mapping, options = normalize_supplier_transform_profile(raw_profile)
            if mapping:
                profiles[supplier_name] = {
                    "target_to_source": ordered_supplier_transform_profile_mapping(mapping),
                    "options": options,
                }

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
        supplier_name = str(raw_supplier_name).strip()
        if supplier_name == "":
            continue
        if not isinstance(raw_profile, dict):
            continue
        mapping, options = normalize_supplier_transform_profile(raw_profile)
        if not mapping:
            continue
        payload_profiles[supplier_name] = {
            "target_to_source": ordered_supplier_transform_profile_mapping(mapping),
            "options": options,
        }

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


def build_supplier_hicore_renamed_copy(
    df_supplier: pd.DataFrame,
    *,
    target_to_source: dict[str, str],
    supplier_name: str,
    strip_leading_zeros_from_sku: bool = False,
    ignore_rows_missing_sku: bool = False,
) -> pd.DataFrame:
    normalized_target_to_source = {
        str(target).strip(): str(source).strip()
        for target, source in target_to_source.items()
        if str(target).strip() in SUPPLIER_HICORE_RENAME_COLUMNS and str(source).strip() != ""
    }
    if not normalized_target_to_source:
        raise ValueError("Matcha minst en HiCore-kolumn innan export.")
    normalized_supplier_name = str(supplier_name).strip()
    if normalized_supplier_name == "":
        raise ValueError("Välj leverantör från leverantörslistan innan export.")

    prepared_df = df_supplier.copy()
    prepared_df.columns = [str(col).strip() for col in prepared_df.columns]

    selected_sources = [str(source).strip() for source in normalized_target_to_source.values()]
    duplicate_sources = find_duplicate_names(selected_sources)
    if duplicate_sources:
        raise ValueError(
            "Samma leverantörskolumn kan inte mappas till flera HiCore-kolumner: "
            + ", ".join(duplicate_sources)
        )

    available_columns = {str(col).strip() for col in prepared_df.columns}
    missing_sources = sorted(
        [source for source in selected_sources if source not in available_columns],
        key=lambda item: item.casefold(),
    )
    if missing_sources:
        raise ValueError(
            "Vald(e) kolumn(er) finns inte i leverantörsfilen: " + ", ".join(missing_sources)
        )

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

    rename_map = {
        str(source).strip(): str(target).strip()
        for target, source in normalized_target_to_source.items()
    }
    ordered_targets = [target for target in SUPPLIER_HICORE_RENAME_COLUMNS if target in normalized_target_to_source]
    ordered_sources = [str(normalized_target_to_source[target]).strip() for target in ordered_targets]
    renamed_df = prepared_df.loc[:, ordered_sources].copy().rename(columns=rename_map)
    renamed_df[SUPPLIER_HICORE_SUPPLIER_COLUMN] = normalized_supplier_name
    renamed_df = renamed_df.loc[
        :,
        [*ordered_targets, SUPPLIER_HICORE_SUPPLIER_COLUMN],
    ]

    output_columns = [str(col).strip() for col in renamed_df.columns]
    duplicate_output_columns = find_duplicate_names(output_columns)
    if duplicate_output_columns:
        raise ValueError(
            "Resultatfilen skulle få dubblettkolumner efter namnbyte: "
            + ", ".join(duplicate_output_columns)
        )

    return renamed_df
