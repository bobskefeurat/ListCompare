from __future__ import annotations

from typing import Optional
import streamlit as st

from listcompare.core.suppliers.prepare import (
    SupplierPrepareAnalysis,
)
from listcompare.core.suppliers.profile import (
    SUPPLIER_HICORE_SKU_COLUMN,
    profile_has_required_sku_mapping as _profile_has_required_sku_mapping,
)
from ...runtime_paths import supplier_index_path as _supplier_index_path
from ...session.file_inputs import render_file_input as _render_file_input
from ...session.navigation import (
    request_supplier_profile_editor as _request_supplier_profile_editor,
    rerun as _rerun,
)
from ...session.profile_access import (
    get_supplier_transform_profile_details as _get_supplier_transform_profile_details,
)
from ...session.run_state import clear_supplier_state as _clear_supplier_state
from ...session.supplier_selection import (
    normalize_selected_supplier_for_options as _normalize_selected_supplier_for_options,
    set_selected_supplier as _set_selected_supplier,
)
from .prepare_state import _sync_supplier_prepare_state
from .actions import (
    build_prepare_signature as _build_prepare_signature,
    evaluate_uploaded_supplier_file as _evaluate_uploaded_supplier_file,
    handle_finalize_supplier_prepare as _handle_finalize_supplier_prepare,
    handle_rebuild_supplier_file as _handle_rebuild_supplier_file,
    handle_run_supplier_compare as _handle_run_supplier_compare,
)
from .results import _render_supplier_results
from .view_model import (
    build_supplier_compare_flags as _build_supplier_compare_flags,
    profile_status_message as _profile_status_message,
    supplier_file_status_message as _supplier_file_status_message,
)
from .conflicts import render_conflict_resolution_block as _render_conflict_resolution_block
from .downloads import render_prepared_supplier_downloads as _render_prepared_supplier_downloads

def _render_supplier_compare_tab(
    *,
    supplier_options: list[str],
    supplier_index_error: Optional[str],
    new_supplier_names: list[str],
    excluded_brands: list[str],
) -> None:
    supplier_index_path = _supplier_index_path()
    _set_selected_supplier(
        st.session_state,
        _normalize_selected_supplier_for_options(
            st.session_state.get("supplier_internal_name"),
            supplier_options,
        ),
        supplier_options,
    )

    hicore_file = _render_file_input(
        session_state=st.session_state,
        kind="hicore",
        label="HiCore-export (.csv/.xlsx/.xls/.xlsm)",
        file_types=["csv", "xlsx", "xls", "xlsm"],
        uploader_key="supplier_hicore_uploader",
    )
    supplier_file = _render_file_input(
        session_state=st.session_state,
        kind="supplier",
        label="Leverantörsfil (.csv/.xlsx/.xls/.xlsm)",
        file_types=["csv", "xlsx", "xls", "xlsm"],
        uploader_key="supplier_file_uploader",
    )
    info_message = st.session_state.get("supplier_compare_info_message")
    if info_message:
        st.success(str(info_message))
        st.session_state["supplier_compare_info_message"] = None

    previous_supplier_name = st.session_state.get("_last_supplier_internal_name")
    supplier_internal_name = st.selectbox(
        "Välj leverantör",
        options=supplier_options,
        index=None,
        placeholder="Välj leverantör...",
        key="supplier_internal_name",
    )
    if previous_supplier_name != supplier_internal_name:
        st.session_state["_last_supplier_internal_name"] = supplier_internal_name
        _clear_supplier_state(st.session_state)
    selected_supplier_name = (
        str(supplier_internal_name).strip() if supplier_internal_name is not None else ""
    )
    _set_selected_supplier(
        st.session_state,
        selected_supplier_name if selected_supplier_name != "" else None,
        supplier_options,
    )

    profile_mapping, profile_composite_fields, profile_filters, profile_options = (
        _get_supplier_transform_profile_details(st.session_state, selected_supplier_name)
    )
    profile_exists = bool(profile_mapping)
    profile_has_required_sku = _profile_has_required_sku_mapping(profile_mapping)
    profile_ready = profile_exists and profile_has_required_sku
    st.session_state["supplier_transform_attention_required"] = (
        selected_supplier_name != "" and not profile_ready
    )

    uploaded_eval = _evaluate_uploaded_supplier_file(
        supplier_file=supplier_file,
        profile_ready=profile_ready,
        profile_mapping=profile_mapping,
        profile_composite_fields=profile_composite_fields,
        profile_filters=profile_filters,
    )
    supplier_file_read_error = uploaded_eval.supplier_file_read_error
    profile_matches_uploaded_file = uploaded_eval.profile_matches_uploaded_file
    file_matches_profile_output_format = uploaded_eval.file_matches_profile_output_format
    missing_profile_columns_for_file = uploaded_eval.missing_profile_columns_for_file
    df_supplier_uploaded = uploaded_eval.df_supplier_uploaded

    current_prepare_signature = _build_prepare_signature(
        supplier_file=supplier_file,
        selected_supplier_name=selected_supplier_name,
        profile_ready=profile_ready,
        supplier_file_read_error=supplier_file_read_error,
        profile_mapping=profile_mapping,
        profile_composite_fields=profile_composite_fields,
        profile_filters=profile_filters,
        profile_options=profile_options,
    )
    _sync_supplier_prepare_state(current_prepare_signature)

    stored_prepare_signature = st.session_state.get("supplier_prepared_signature")
    prepared_supplier_df = st.session_state.get("supplier_prepared_df")
    prepared_excluded_normalized_skus_state = st.session_state.get(
        "supplier_prepared_excluded_normalized_skus"
    )
    prepared_excluded_normalized_skus = (
        prepared_excluded_normalized_skus_state
        if isinstance(prepared_excluded_normalized_skus_state, frozenset)
        else frozenset()
    )
    prepared_file_name = st.session_state.get("supplier_prepared_file_name")
    prepared_excel_bytes = st.session_state.get("supplier_prepared_excel_bytes")
    ignored_rows_df = st.session_state.get("supplier_ignored_rows_df")
    ignored_rows_file_name = st.session_state.get("supplier_ignored_rows_file_name")
    ignored_rows_excel_bytes = st.session_state.get("supplier_ignored_rows_excel_bytes")
    prepare_analysis_state = st.session_state.get("supplier_prepare_analysis")
    prepare_analysis = (
        prepare_analysis_state
        if isinstance(prepare_analysis_state, SupplierPrepareAnalysis)
        else None
    )
    flags = _build_supplier_compare_flags(
        supplier_file_present=supplier_file is not None,
        hicore_file_present=hicore_file is not None,
        selected_supplier_name=selected_supplier_name,
        profile_exists=profile_exists,
        profile_ready=profile_ready,
        supplier_file_read_error=supplier_file_read_error,
        file_matches_profile_output_format=file_matches_profile_output_format,
        profile_matches_uploaded_file=profile_matches_uploaded_file,
        df_supplier_uploaded=df_supplier_uploaded,
        current_prepare_signature=current_prepare_signature,
        stored_prepare_signature=stored_prepare_signature,
        prepared_supplier_df=prepared_supplier_df,
        prepare_analysis=prepare_analysis,
    )
    has_prepared_supplier_df = flags.has_prepared_supplier_df
    has_pending_conflicts = flags.has_pending_conflicts

    profile_status = _profile_status_message(
        selected_supplier_name=selected_supplier_name,
        profile_exists=profile_exists,
        profile_has_required_sku=profile_has_required_sku,
        sku_column_name=SUPPLIER_HICORE_SKU_COLUMN,
    )
    getattr(st, profile_status.level)(profile_status.text)

    file_status = _supplier_file_status_message(
        supplier_file_present=supplier_file is not None,
        supplier_file_read_error=supplier_file_read_error,
        profile_ready=profile_ready,
        file_matches_profile_output_format=file_matches_profile_output_format,
        profile_matches_uploaded_file=profile_matches_uploaded_file,
        missing_profile_columns_for_file=missing_profile_columns_for_file,
    )
    if file_status is not None:
        getattr(st, file_status.level)(file_status.text)

    rebuild_col, profile_col = st.columns(2)
    if rebuild_col.button(
        "Bygg om till Hicore-format",
        type="secondary",
        disabled=not flags.can_prepare_uploaded_file,
        key="rebuild_supplier_file_with_profile_button",
    ):
        _handle_rebuild_supplier_file(
            current_prepare_signature=current_prepare_signature,
            df_supplier_uploaded=df_supplier_uploaded,
            selected_supplier_name=selected_supplier_name,
            profile_mapping=profile_mapping,
            profile_composite_fields=profile_composite_fields,
            profile_filters=profile_filters,
            profile_options=profile_options,
        )

    if profile_col.button(
        flags.profile_action_label,
        type="secondary",
        disabled=not flags.can_manage_profile,
        key="update_supplier_profile_button",
    ):
        _request_supplier_profile_editor(st.session_state, selected_supplier_name)

    if flags.show_prepare_hint:
        st.info('Bygg om till Hicore-format innan du kör jämförelsen.')

    if has_pending_conflicts and prepare_analysis is not None and current_prepare_signature is not None:
        conflict_render_result = _render_conflict_resolution_block(
            prepare_analysis=prepare_analysis,
            current_prepare_signature=current_prepare_signature,
        )
        if conflict_render_result.should_rerun:
            _rerun()
        if conflict_render_result.finalize_requested:
            _handle_finalize_supplier_prepare(
                prepare_analysis=prepare_analysis,
                current_choices=conflict_render_result.current_choices,
                current_prepare_signature=current_prepare_signature,
                selected_supplier_name=selected_supplier_name,
            )

    if has_prepared_supplier_df:
        _render_prepared_supplier_downloads(
            prepared_excel_bytes=prepared_excel_bytes,
            prepared_file_name=prepared_file_name,
            ignored_rows_excel_bytes=ignored_rows_excel_bytes,
            ignored_rows_file_name=ignored_rows_file_name,
            ignored_rows_df=ignored_rows_df,
        )

    run_clicked = st.button(
        "Kör Jämförelse",
        type="primary",
        disabled=not flags.can_run,
        key="run_supplier_button",
    )

    if run_clicked:
        _handle_run_supplier_compare(
            hicore_file=hicore_file,  # type: ignore[arg-type]
            selected_supplier_name=selected_supplier_name,
            prepared_supplier_df=prepared_supplier_df,  # type: ignore[arg-type]
            excluded_brands=excluded_brands,
            profile_excluded_normalized_skus=prepared_excluded_normalized_skus,
        )

    st.caption(f"Antal leverantörer: {len(supplier_options)}")
    if new_supplier_names:
        st.success(
            f"Uppdaterade {supplier_index_path.name} med {len(new_supplier_names)} ny(a) leverantör(er) från HiCore."
        )
    if supplier_index_error:
        st.warning(
            f"Kunde inte läsa {supplier_index_path.name} vid uppstart: {supplier_index_error}"
        )

    if st.session_state["supplier_ui_error"]:
        st.error(st.session_state["supplier_ui_error"])
    if st.session_state["supplier_ui_result"] is not None:
        _render_supplier_results(
            st.session_state["supplier_ui_result"],
            supplier_name=selected_supplier_name,
        )


