from __future__ import annotations

import pandas as pd

from .models import _SOURCE_ROW_COLUMN, SUPPLIER_PREPARE_IGNORE_GROUP, SupplierPrepareAnalysis


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
