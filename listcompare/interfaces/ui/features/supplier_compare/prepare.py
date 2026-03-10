from __future__ import annotations

import pandas as pd

from listcompare.core.suppliers.prepare import (
    SUPPLIER_PREPARE_IGNORE_GROUP,
    SupplierPrepareAnalysis,
)


def _prepared_supplier_success_message(
    *,
    supplier_name: str,
    exact_duplicate_rows_removed: int,
) -> str:
    if exact_duplicate_rows_removed > 0:
        return (
            f'Leverantörsfilen för "{supplier_name}" är klar för jämförelse. '
            f"{exact_duplicate_rows_removed} exakta dublettrad(er) togs bort."
        )
    return f'Leverantörsfilen för "{supplier_name}" är klar för jämförelse.'


def _build_ignored_rows_df(
    *,
    analysis: SupplierPrepareAnalysis,
    selected_candidates: dict[str, str],
) -> pd.DataFrame:
    selected_by_group = {
        str(group_key).strip(): str(candidate_id).strip()
        for group_key, candidate_id in selected_candidates.items()
        if str(group_key).strip() != "" and str(candidate_id).strip() != ""
    }
    output_columns = list(analysis.output_columns)
    ignored_rows: list[tuple[int, dict[str, object]]] = []

    for conflict in analysis.conflicts:
        selected_candidate_id = selected_by_group.get(conflict.group_key, "")
        if selected_candidate_id == "":
            continue
        if selected_candidate_id == SUPPLIER_PREPARE_IGNORE_GROUP:
            ignored_candidates = tuple(conflict.candidates)
        else:
            ignored_candidates = tuple(
                candidate
                for candidate in conflict.candidates
                if candidate.candidate_id != selected_candidate_id
            )

        for candidate in ignored_candidates:
            for source_row_number in candidate.source_row_numbers:
                ignored_row: dict[str, object] = {}
                for column_name in output_columns:
                    ignored_row[column_name] = candidate.row_values.get(column_name, "")
                ignored_rows.append((int(source_row_number), ignored_row))

    if not ignored_rows:
        return pd.DataFrame(columns=output_columns)

    sorted_rows = [row for _source_row, row in sorted(ignored_rows, key=lambda item: item[0])]
    ignored_df = pd.DataFrame(sorted_rows, columns=output_columns)
    return ignored_df.reset_index(drop=True)

