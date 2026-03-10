from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd
import streamlit as st

from listcompare.core.suppliers.prepare import (
    SUPPLIER_PREPARE_IGNORE_GROUP,
    SupplierDuplicateConflict,
    SupplierPrepareAnalysis,
)

from ...session.navigation import rerun as _rerun


@dataclass(frozen=True)
class ConflictResolutionRenderResult:
    should_rerun: bool
    finalize_requested: bool
    current_choices: dict[str, str]


def _ignore_all_conflict_choices(
    *,
    prepare_analysis: SupplierPrepareAnalysis,
) -> dict[str, str]:
    return {
        conflict.group_key: SUPPLIER_PREPARE_IGNORE_GROUP
        for conflict in prepare_analysis.conflicts
    }


def _render_prepare_conflict_group(
    *,
    conflict: SupplierDuplicateConflict,
    prepare_signature: str,
    stored_choices: dict[str, str],
) -> Optional[str]:
    sku_text = str(conflict.sku).strip() or "(tomt SKU)"

    selection_key = f"supplier_prepare_choice_editor_{prepare_signature}_{conflict.group_key}"
    ignore_key = f"supplier_prepare_ignore_{prepare_signature}_{conflict.group_key}"
    stored_choice = str(stored_choices.get(conflict.group_key, "")).strip()
    if ignore_key not in st.session_state:
        st.session_state[ignore_key] = stored_choice == SUPPLIER_PREPARE_IGNORE_GROUP

    is_resolved = stored_choice != ""
    if stored_choice == SUPPLIER_PREPARE_IGNORE_GROUP:
        status_text = "Ignorerad"
    elif is_resolved:
        status_text = "Vald"
    else:
        status_text = ""
    expander_label = f"SKU: {sku_text}"
    if status_text != "":
        expander_label = f"{expander_label} ({status_text})"

    with st.expander(expander_label, expanded=not is_resolved):
        candidate_rows: list[dict[str, object]] = []
        candidate_ids_by_row_index: list[str] = []
        for candidate in conflict.candidates:
            candidate_ids_by_row_index.append(candidate.candidate_id)
            candidate_rows.append(
                {
                    "Välj": candidate.candidate_id == stored_choice,
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
        if "Välj" in selected_df.columns:
            selected_row_indexes = [
                int(index)
                for index in selected_df.index[selected_df["Välj"] == True].tolist()
            ]
            selected_candidate_ids = [
                candidate_ids_by_row_index[index]
                for index in selected_row_indexes
                if 0 <= index < len(candidate_ids_by_row_index)
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

    return None


def render_conflict_resolution_block(
    *,
    prepare_analysis: SupplierPrepareAnalysis,
    current_prepare_signature: str,
) -> ConflictResolutionRenderResult:
    st.error(
        "Konfliktdubletter hittades i leverantörsfilen. "
        "Välj vilken rad som gäller per SKU innan filen kan byggas klart."
    )
    if prepare_analysis.exact_duplicate_rows_removed > 0:
        st.info(
            f"{prepare_analysis.exact_duplicate_rows_removed} exakta dublettrad(er) "
            "togs bort automatiskt innan konfliktlistan skapades."
        )

    stored_choices_raw = st.session_state.get("supplier_prepare_resolution_choices", {})
    stored_choices = stored_choices_raw if isinstance(stored_choices_raw, dict) else {}
    if st.button(
        "Ignorera alla",
        type="secondary",
        key="ignore_all_supplier_prepare_conflicts_button",
    ):
        ignore_all_choices = _ignore_all_conflict_choices(prepare_analysis=prepare_analysis)
        st.session_state["supplier_prepare_resolution_choices"] = ignore_all_choices
        for conflict in prepare_analysis.conflicts:
            ignore_key = (
                f"supplier_prepare_ignore_{current_prepare_signature}_{conflict.group_key}"
            )
            st.session_state[ignore_key] = True
        return ConflictResolutionRenderResult(
            should_rerun=True,
            finalize_requested=False,
            current_choices=ignore_all_choices,
        )

    current_choices: dict[str, str] = {}
    for conflict in prepare_analysis.conflicts:
        selected_candidate_id = _render_prepare_conflict_group(
            conflict=conflict,
            prepare_signature=current_prepare_signature,
            stored_choices=stored_choices,
        )
        if selected_candidate_id is not None and str(selected_candidate_id).strip() != "":
            current_choices[conflict.group_key] = str(selected_candidate_id).strip()

    st.session_state["supplier_prepare_resolution_choices"] = current_choices
    should_rerun = current_choices != stored_choices
    all_conflicts_resolved = all(
        conflict.group_key in current_choices for conflict in prepare_analysis.conflicts
    )
    finalize_requested = st.button(
        "Slutför byggning",
        type="primary",
        disabled=not all_conflicts_resolved,
        key="finalize_supplier_prepare_button",
    )
    return ConflictResolutionRenderResult(
        should_rerun=should_rerun,
        finalize_requested=finalize_requested,
        current_choices=current_choices,
    )

