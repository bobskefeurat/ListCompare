from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from ....supplier_prepare_utils import (
    SupplierDuplicateConflict,
    SupplierPrepareAnalysis,
    SUPPLIER_PREPARE_IGNORE_GROUP,
)
from ....supplier_profile_utils import rebuilt_supplier_file_name as _rebuilt_supplier_file_name
from ...data_io import _df_excel_bytes
from ...state import _clear_supplier_state, _rerun


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


def _ignored_rows_file_name(*, supplier_name: str) -> str:
    rebuilt_name = _rebuilt_supplier_file_name(supplier_name=supplier_name, extension=".xlsx")
    return rebuilt_name.replace("_prislista_", "_ignorerade_rader_", 1)


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
    ignored_columns = [
        "Konfliktgrupp",
        "KonfliktSKU",
        "Ignoreringsorsak",
        "Kallrad",
        *output_columns,
    ]
    ignored_rows: list[dict[str, object]] = []

    for conflict in analysis.conflicts:
        selected_candidate_id = selected_by_group.get(conflict.group_key, "")
        if selected_candidate_id == "":
            continue
        if selected_candidate_id == SUPPLIER_PREPARE_IGNORE_GROUP:
            ignored_candidates = tuple(conflict.candidates)
            ignored_reason = "Ignorerad grupp"
        else:
            ignored_candidates = tuple(
                candidate
                for candidate in conflict.candidates
                if candidate.candidate_id != selected_candidate_id
            )
            ignored_reason = "Ej valt alternativ"

        for candidate in ignored_candidates:
            for source_row_number in candidate.source_row_numbers:
                ignored_row: dict[str, object] = {
                    "Konfliktgrupp": conflict.group_key,
                    "KonfliktSKU": str(conflict.sku).strip(),
                    "Ignoreringsorsak": ignored_reason,
                    "Kallrad": int(source_row_number),
                }
                for column_name in output_columns:
                    ignored_row[column_name] = candidate.row_values.get(column_name, "")
                ignored_rows.append(ignored_row)

    if not ignored_rows:
        return pd.DataFrame(columns=ignored_columns)

    ignored_df = pd.DataFrame(ignored_rows, columns=ignored_columns)
    ignored_df = ignored_df.sort_values(
        by=["Kallrad", "Konfliktgrupp"],
        kind="stable",
    )
    return ignored_df.reset_index(drop=True)


def _store_prepared_supplier_df(
    *,
    prepared_df: pd.DataFrame,
    ignored_rows_df: pd.DataFrame,
    prepare_signature: str,
    supplier_name: str,
) -> None:
    st.session_state["supplier_prepared_df"] = prepared_df
    st.session_state["supplier_prepared_signature"] = prepare_signature
    st.session_state["supplier_prepared_file_name"] = _rebuilt_supplier_file_name(supplier_name)
    st.session_state["supplier_prepared_excel_bytes"] = _df_excel_bytes(
        prepared_df,
        sheet_name="HiCore-format",
    )
    st.session_state["supplier_ignored_rows_df"] = ignored_rows_df
    if ignored_rows_df.empty:
        st.session_state["supplier_ignored_rows_file_name"] = None
        st.session_state["supplier_ignored_rows_excel_bytes"] = None
    else:
        st.session_state["supplier_ignored_rows_file_name"] = _ignored_rows_file_name(
            supplier_name=supplier_name
        )
        st.session_state["supplier_ignored_rows_excel_bytes"] = _df_excel_bytes(
            ignored_rows_df,
            sheet_name="Ignorerade rader",
        )
    st.session_state["supplier_prepare_analysis"] = None
    st.session_state["supplier_prepare_resolution_choices"] = {}


def _sync_supplier_prepare_state(current_signature: Optional[str]) -> None:
    stored_signature = st.session_state.get("supplier_prepared_signature")
    has_pending_analysis = st.session_state.get("supplier_prepare_analysis") is not None
    has_prepared_df = st.session_state.get("supplier_prepared_df") is not None
    if not has_pending_analysis and not has_prepared_df and stored_signature is None:
        return
    if stored_signature != current_signature:
        _clear_supplier_state()


def _render_prepare_conflict_group(
    *,
    conflict: SupplierDuplicateConflict,
    prepare_signature: str,
    stored_choices: dict[str, str],
) -> Optional[str]:
    sku_text = str(conflict.sku).strip() or "(tomt SKU)"
    st.markdown(f"**SKU: {sku_text}**")

    selection_key = f"supplier_prepare_choice_editor_{prepare_signature}_{conflict.group_key}"
    ignore_key = f"supplier_prepare_ignore_{prepare_signature}_{conflict.group_key}"
    stored_choice = str(stored_choices.get(conflict.group_key, "")).strip()
    if ignore_key not in st.session_state:
        st.session_state[ignore_key] = stored_choice == SUPPLIER_PREPARE_IGNORE_GROUP

    candidate_rows: list[dict[str, object]] = []
    option_label_to_candidate_id: dict[str, str] = {}
    for candidate_index, candidate in enumerate(conflict.candidates, start=1):
        option_label = f"Alternativ {candidate_index}"
        option_label_to_candidate_id[option_label] = candidate.candidate_id
        candidate_rows.append(
            {
                "Välj": candidate.candidate_id == stored_choice,
                "Alternativ": option_label,
                **candidate.row_values,
            }
        )

    selection_col, ignore_col = st.columns([4, 1])
    ignore_active = bool(st.session_state.get(ignore_key, False))
    selected_df = selection_col.data_editor(
        pd.DataFrame(candidate_rows),
        use_container_width=True,
        hide_index=True,
        key=selection_key,
        disabled=ignore_active,
    )

    selected_candidate_ids: list[str] = []
    if "Välj" in selected_df.columns and "Alternativ" in selected_df.columns:
        selected_option_labels = [
            str(label)
            for label in selected_df.loc[selected_df["Välj"] == True, "Alternativ"].tolist()
        ]
        selected_candidate_ids = [
            option_label_to_candidate_id[label]
            for label in selected_option_labels
            if label in option_label_to_candidate_id
        ]

    button_label = "Ångra ignorering" if ignore_active else "Ignorera grupp"
    if ignore_col.button(
        button_label,
        type="secondary",
        key=f"{ignore_key}_button",
    ):
        st.session_state[ignore_key] = not ignore_active
        _rerun()

    if bool(st.session_state.get(ignore_key, False)):
        st.info(f"SKU {sku_text} ignoreras när leverantörsfilen byggs.")
        return SUPPLIER_PREPARE_IGNORE_GROUP

    if len(selected_candidate_ids) > 1:
        st.warning(f"Välj exakt ett alternativ för SKU {sku_text}.")
        return None
    if not selected_candidate_ids:
        return None
    return selected_candidate_ids[0]


