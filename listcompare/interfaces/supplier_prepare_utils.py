from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from ..core.product_diff import normalize_sku
from .supplier_profile_utils import (
    SUPPLIER_HICORE_RENAME_COLUMNS,
    SUPPLIER_HICORE_SKU_COLUMN,
    SUPPLIER_HICORE_SUPPLIER_COLUMN,
    SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN,
    SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES,
    SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU,
    SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS,
    build_supplier_hicore_renamed_copy,
    matches_profile_output_format,
    missing_profile_source_columns,
    normalize_supplier_transform_profile_composite_fields,
    normalize_supplier_transform_profile_filters,
    normalize_supplier_transform_profile_mapping,
    normalize_supplier_transform_profile_options,
    ordered_supplier_transform_profile_composite_fields,
    ordered_supplier_transform_profile_mapping,
)

_SOURCE_ROW_COLUMN = "__lc_source_row_number"
SUPPLIER_PREPARE_IGNORE_GROUP = "__ignore_conflict_group__"


@dataclass(frozen=True)
class SupplierConflictCandidate:
    candidate_id: str
    source_row_numbers: tuple[int, ...]
    row_values: dict[str, str]


@dataclass(frozen=True)
class SupplierDuplicateConflict:
    group_key: str
    sku: str
    candidates: tuple[SupplierConflictCandidate, ...]


@dataclass(frozen=True)
class SupplierPrepareAnalysis:
    output_columns: tuple[str, ...]
    exact_duplicate_rows_removed: int
    rows_ready_without_conflicts: pd.DataFrame
    conflicts: tuple[SupplierDuplicateConflict, ...]


def _prepared_value_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.casefold() == "nan":
        return ""
    return text


def _canonicalize_prepared_output_df(df_supplier: pd.DataFrame) -> pd.DataFrame:
    prepared_df = df_supplier.copy()
    prepared_df.columns = [str(column).strip() for column in prepared_df.columns]

    available_columns = {str(column).strip() for column in prepared_df.columns}
    output_columns = [
        column_name
        for column_name in SUPPLIER_HICORE_RENAME_COLUMNS
        if column_name in available_columns
    ]
    if SUPPLIER_HICORE_SUPPLIER_COLUMN not in available_columns:
        raise ValueError(
            f'Den uppladdade leverantörsfilen saknar "{SUPPLIER_HICORE_SUPPLIER_COLUMN}".'
        )
    output_columns.append(SUPPLIER_HICORE_SUPPLIER_COLUMN)

    canonical_df = prepared_df.loc[:, output_columns].copy()
    canonical_df[_SOURCE_ROW_COLUMN] = canonical_df.index.map(lambda raw_index: int(raw_index) + 2)
    return canonical_df.reset_index(drop=True)


def supplier_prepare_signature(
    *,
    supplier_name: str,
    supplier_file_name: str,
    supplier_bytes: bytes,
    profile_mapping: Optional[dict[str, str]] = None,
    profile_composite_fields: Optional[dict[str, list[str]]] = None,
    profile_filters: Optional[dict[str, object]] = None,
    profile_options: Optional[dict[str, bool]] = None,
) -> str:
    normalized_profile_mapping = normalize_supplier_transform_profile_mapping(
        profile_mapping if isinstance(profile_mapping, dict) else {}
    )
    normalized_profile_composite_fields = normalize_supplier_transform_profile_composite_fields(
        profile_composite_fields if isinstance(profile_composite_fields, dict) else {}
    )
    normalized_profile_filters = normalize_supplier_transform_profile_filters(
        profile_filters if isinstance(profile_filters, dict) else {}
    )
    normalized_profile_options = normalize_supplier_transform_profile_options(
        profile_options if isinstance(profile_options, dict) else {}
    )

    payload = {
        "supplier_name": str(supplier_name).strip(),
        "supplier_file_name": str(supplier_file_name).strip(),
        "supplier_file_sha1": hashlib.sha1(supplier_bytes).hexdigest(),
        "profile_mapping": ordered_supplier_transform_profile_mapping(
            normalized_profile_mapping
        ),
        "profile_composite_fields": ordered_supplier_transform_profile_composite_fields(
            normalized_profile_composite_fields
        ),
        "profile_filters": {
            SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN: str(
                normalized_profile_filters[SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN]
            ).strip(),
            SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES: [
                str(value)
                for value in normalized_profile_filters[
                    SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES
                ]
            ],
        },
        "profile_options": {
            SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS: bool(
                normalized_profile_options[SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS]
            ),
            SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU: bool(
                normalized_profile_options[SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU]
            ),
        },
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()


def _candidate_signature(
    row_values: dict[str, str],
    *,
    normalized_sku: str,
    output_columns: list[str],
) -> tuple[tuple[str, str], ...]:
    signature_items: list[tuple[str, str]] = [(SUPPLIER_HICORE_SKU_COLUMN, normalized_sku)]
    for column_name in output_columns:
        if column_name == SUPPLIER_HICORE_SKU_COLUMN:
            continue
        signature_items.append((column_name, row_values.get(column_name, "")))
    return tuple(signature_items)


def build_supplier_prepare_analysis(
    df_supplier: pd.DataFrame,
    *,
    supplier_name: str,
    profile_mapping: Optional[dict[str, str]] = None,
    profile_composite_fields: Optional[dict[str, list[str]]] = None,
    profile_filters: Optional[dict[str, object]] = None,
    profile_options: Optional[dict[str, bool]] = None,
) -> SupplierPrepareAnalysis:
    normalized_profile_mapping = normalize_supplier_transform_profile_mapping(
        profile_mapping if isinstance(profile_mapping, dict) else {}
    )
    normalized_profile_composite_fields = normalize_supplier_transform_profile_composite_fields(
        profile_composite_fields if isinstance(profile_composite_fields, dict) else {}
    )
    normalized_profile_filters = normalize_supplier_transform_profile_filters(
        profile_filters if isinstance(profile_filters, dict) else {}
    )
    normalized_profile_options = normalize_supplier_transform_profile_options(
        profile_options if isinstance(profile_options, dict) else {}
    )

    source_columns = [str(column).strip() for column in df_supplier.columns]
    if matches_profile_output_format(
        normalized_profile_mapping,
        source_columns,
        composite_fields=normalized_profile_composite_fields,
    ):
        prepared_df = _canonicalize_prepared_output_df(df_supplier)
    else:
        missing_columns = missing_profile_source_columns(
            normalized_profile_mapping,
            source_columns,
            composite_fields=normalized_profile_composite_fields,
            filters=normalized_profile_filters,
        )
        if missing_columns:
            raise ValueError(
                "Uppladdad leverantörsfil matchar inte profilen. Saknade kolumner: "
                + ", ".join(missing_columns)
            )

        prepared_df = build_supplier_hicore_renamed_copy(
            df_supplier,
            target_to_source=normalized_profile_mapping,
            supplier_name=supplier_name,
            composite_fields=normalized_profile_composite_fields,
            brand_source_column=str(
                normalized_profile_filters[SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN]
            ),
            excluded_brand_values=[
                str(value)
                for value in normalized_profile_filters[
                    SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES
                ]
            ],
            strip_leading_zeros_from_sku=normalized_profile_options[
                SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS
            ],
            ignore_rows_missing_sku=normalized_profile_options[
                SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU
            ],
            source_row_column=_SOURCE_ROW_COLUMN,
        )

    output_columns = [
        column_name
        for column_name in prepared_df.columns
        if column_name != _SOURCE_ROW_COLUMN
    ]
    if SUPPLIER_HICORE_SKU_COLUMN not in output_columns:
        raise ValueError(
            f'Den ombyggda leverantörsfilen saknar "{SUPPLIER_HICORE_SKU_COLUMN}".'
        )

    grouped_rows: dict[str, list[tuple[int, dict[str, str]]]] = {}
    for _, row in prepared_df.iterrows():
        row_values = {
            column_name: _prepared_value_text(row.get(column_name, ""))
            for column_name in output_columns
        }
        normalized_sku = normalize_sku(row_values.get(SUPPLIER_HICORE_SKU_COLUMN, ""))
        source_row_number = int(row.get(_SOURCE_ROW_COLUMN, 0))
        grouped_rows.setdefault(normalized_sku, []).append((source_row_number, row_values))

    exact_duplicate_rows_removed = 0
    ready_rows: list[dict[str, object]] = []
    conflicts: list[SupplierDuplicateConflict] = []

    for group_index, (normalized_sku, group_rows) in enumerate(grouped_rows.items(), start=1):
        unique_candidates: dict[tuple[tuple[str, str], ...], dict[str, object]] = {}
        for source_row_number, row_values in group_rows:
            signature = _candidate_signature(
                row_values,
                normalized_sku=normalized_sku,
                output_columns=output_columns,
            )
            candidate_data = unique_candidates.get(signature)
            if candidate_data is None:
                unique_candidates[signature] = {
                    "row_values": dict(row_values),
                    "source_row_numbers": [source_row_number],
                }
                continue
            candidate_data["source_row_numbers"].append(source_row_number)

        exact_duplicate_rows_removed += len(group_rows) - len(unique_candidates)

        if len(unique_candidates) == 1:
            candidate_data = next(iter(unique_candidates.values()))
            ready_row = dict(candidate_data["row_values"])
            ready_row[_SOURCE_ROW_COLUMN] = candidate_data["source_row_numbers"][0]
            ready_rows.append(ready_row)
            continue

        group_key = f"supplier_prepare_conflict_{group_index}"
        candidates: list[SupplierConflictCandidate] = []
        display_sku = ""
        for candidate_index, candidate_data in enumerate(unique_candidates.values(), start=1):
            candidate_row_values = dict(candidate_data["row_values"])
            if display_sku == "":
                display_sku = candidate_row_values.get(SUPPLIER_HICORE_SKU_COLUMN, "")
            candidates.append(
                SupplierConflictCandidate(
                    candidate_id=f"{group_key}_candidate_{candidate_index}",
                    source_row_numbers=tuple(
                        int(row_number) for row_number in candidate_data["source_row_numbers"]
                    ),
                    row_values=candidate_row_values,
                )
            )

        conflicts.append(
            SupplierDuplicateConflict(
                group_key=group_key,
                sku=display_sku,
                candidates=tuple(candidates),
            )
        )

    rows_ready_without_conflicts = pd.DataFrame(
        ready_rows,
        columns=[*output_columns, _SOURCE_ROW_COLUMN],
    )
    if not rows_ready_without_conflicts.empty:
        rows_ready_without_conflicts = rows_ready_without_conflicts.sort_values(
            by=[_SOURCE_ROW_COLUMN],
            kind="stable",
        ).reset_index(drop=True)

    return SupplierPrepareAnalysis(
        output_columns=tuple(output_columns),
        exact_duplicate_rows_removed=exact_duplicate_rows_removed,
        rows_ready_without_conflicts=rows_ready_without_conflicts,
        conflicts=tuple(conflicts),
    )


def finalize_supplier_prepare_analysis(
    analysis: SupplierPrepareAnalysis,
    *,
    selected_candidates: dict[str, str],
) -> pd.DataFrame:
    selected_by_group = {
        str(group_key).strip(): str(candidate_id).strip()
        for group_key, candidate_id in selected_candidates.items()
        if str(group_key).strip() != "" and str(candidate_id).strip() != ""
    }

    final_frames: list[pd.DataFrame] = []
    if not analysis.rows_ready_without_conflicts.empty:
        final_frames.append(analysis.rows_ready_without_conflicts.copy())

    for conflict in analysis.conflicts:
        selected_candidate_id = selected_by_group.get(conflict.group_key, "")
        if selected_candidate_id == SUPPLIER_PREPARE_IGNORE_GROUP:
            continue
        if selected_candidate_id == "":
            sku_text = conflict.sku if str(conflict.sku).strip() != "" else "(tomt SKU)"
            raise ValueError(f"Välj vilken rad som gäller för SKU {sku_text}.")

        selected_candidate = next(
            (
                candidate
                for candidate in conflict.candidates
                if candidate.candidate_id == selected_candidate_id
            ),
            None,
        )
        if selected_candidate is None:
            sku_text = conflict.sku if str(conflict.sku).strip() != "" else "(tomt SKU)"
            raise ValueError(f"Ogiltigt val för SKU {sku_text}.")

        selected_row = dict(selected_candidate.row_values)
        selected_row[_SOURCE_ROW_COLUMN] = selected_candidate.source_row_numbers[0]
        final_frames.append(
            pd.DataFrame(
                [selected_row],
                columns=[*analysis.output_columns, _SOURCE_ROW_COLUMN],
            )
        )

    if final_frames:
        final_df = pd.concat(final_frames, ignore_index=True)
    else:
        final_df = pd.DataFrame(columns=[*analysis.output_columns, _SOURCE_ROW_COLUMN])

    if _SOURCE_ROW_COLUMN in final_df.columns:
        final_df = final_df.sort_values(by=[_SOURCE_ROW_COLUMN], kind="stable")
        final_df = final_df.drop(columns=[_SOURCE_ROW_COLUMN])

    return final_df.loc[:, list(analysis.output_columns)].reset_index(drop=True)
