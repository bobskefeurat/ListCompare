from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd
import streamlit as st

from listcompare.core.suppliers.prepare import (
    SupplierPrepareAnalysis,
    build_supplier_prepare_analysis as _build_supplier_prepare_analysis,
    finalize_supplier_prepare_analysis as _finalize_supplier_prepare_analysis,
    supplier_prepare_signature as _supplier_prepare_signature,
)
from listcompare.core.suppliers.profile import (
    matches_profile_output_format as _matches_profile_output_format,
    missing_profile_source_columns as _missing_profile_source_columns,
)
from ...io.uploads import _read_supplier_upload
from ...shared.presentation import build_progress_updater as _build_progress_updater
from ...services.supplier_compute import compute_supplier_result as _compute_supplier_result
from ...session.navigation import rerun as _rerun
from ...session.run_state import (
    clear_supplier_prepare_state as _clear_supplier_prepare_state,
    clear_supplier_result_state as _clear_supplier_result_state,
)
from .prepare import (
    _build_ignored_rows_df,
    _prepared_supplier_success_message,
)
from .prepare_state import _store_prepared_supplier_df


@dataclass(frozen=True)
class UploadedSupplierEvaluation:
    df_supplier_uploaded: Optional[pd.DataFrame]
    supplier_file_read_error: Optional[str]
    profile_matches_uploaded_file: bool
    file_matches_profile_output_format: bool
    missing_profile_columns_for_file: list[str]


def evaluate_uploaded_supplier_file(
    *,
    supplier_file: Optional[dict[str, object]],
    profile_ready: bool,
    profile_mapping: dict[str, str],
    profile_composite_fields: dict[str, list[str]],
    profile_filters: dict[str, object],
) -> UploadedSupplierEvaluation:
    if supplier_file is None:
        return UploadedSupplierEvaluation(
            df_supplier_uploaded=None,
            supplier_file_read_error=None,
            profile_matches_uploaded_file=False,
            file_matches_profile_output_format=False,
            missing_profile_columns_for_file=[],
        )

    supplier_file_name = str(supplier_file["name"])  # type: ignore[index]
    supplier_bytes = supplier_file["bytes"]  # type: ignore[index]
    try:
        df_supplier_uploaded = _read_supplier_upload(supplier_file_name, supplier_bytes)
    except Exception as exc:
        return UploadedSupplierEvaluation(
            df_supplier_uploaded=None,
            supplier_file_read_error=str(exc),
            profile_matches_uploaded_file=False,
            file_matches_profile_output_format=False,
            missing_profile_columns_for_file=[],
        )

    missing_profile_columns_for_file: list[str] = []
    profile_matches_uploaded_file = False
    file_matches_profile_output_format = False
    if profile_ready:
        source_columns = [str(column).strip() for column in df_supplier_uploaded.columns]
        missing_profile_columns_for_file = _missing_profile_source_columns(
            profile_mapping,
            source_columns,
            composite_fields=profile_composite_fields,
            filters=profile_filters,
        )
        profile_matches_uploaded_file = len(missing_profile_columns_for_file) == 0
        file_matches_profile_output_format = _matches_profile_output_format(
            profile_mapping,
            source_columns,
            composite_fields=profile_composite_fields,
        )

    return UploadedSupplierEvaluation(
        df_supplier_uploaded=df_supplier_uploaded,
        supplier_file_read_error=None,
        profile_matches_uploaded_file=profile_matches_uploaded_file,
        file_matches_profile_output_format=file_matches_profile_output_format,
        missing_profile_columns_for_file=missing_profile_columns_for_file,
    )


def build_prepare_signature(
    *,
    supplier_file: Optional[dict[str, object]],
    selected_supplier_name: str,
    profile_ready: bool,
    supplier_file_read_error: Optional[str],
    profile_mapping: dict[str, str],
    profile_composite_fields: dict[str, list[str]],
    profile_filters: dict[str, object],
    profile_options: dict[str, bool],
) -> Optional[str]:
    if (
        supplier_file is None
        or selected_supplier_name == ""
        or not profile_ready
        or supplier_file_read_error is not None
    ):
        return None
    return _supplier_prepare_signature(
        supplier_name=selected_supplier_name,
        supplier_file_name=str(supplier_file["name"]),  # type: ignore[index]
        supplier_bytes=supplier_file["bytes"],  # type: ignore[index]
        profile_mapping=profile_mapping,
        profile_composite_fields=profile_composite_fields,
        profile_filters=profile_filters,
        profile_options=profile_options,
    )


def handle_rebuild_supplier_file(
    *,
    current_prepare_signature: Optional[str],
    df_supplier_uploaded: Optional[pd.DataFrame],
    selected_supplier_name: str,
    profile_mapping: dict[str, str],
    profile_composite_fields: dict[str, list[str]],
    profile_filters: dict[str, object],
    profile_options: dict[str, bool],
) -> None:
    update_progress, clear_progress = _build_progress_updater(label="Bygg om leverantörsfil")
    update_progress(0.0, "Startar")
    try:
        if current_prepare_signature is None or df_supplier_uploaded is None:
            raise ValueError("Ladda upp en leverantörsfil som matchar profilen innan du bygger.")

        update_progress(0.20, "Analyserar fil")
        prepare_analysis = _build_supplier_prepare_analysis(
            df_supplier_uploaded,
            supplier_name=selected_supplier_name,
            profile_mapping=profile_mapping,
            profile_composite_fields=profile_composite_fields,
            profile_filters=profile_filters,
            profile_options=profile_options,
        )
        st.session_state["supplier_prepared_signature"] = current_prepare_signature
        st.session_state["supplier_prepare_analysis"] = prepare_analysis
        st.session_state["supplier_prepare_resolution_choices"] = {}
        st.session_state["supplier_prepared_df"] = None
        st.session_state["supplier_prepared_excluded_normalized_skus"] = frozenset()
        st.session_state["supplier_prepared_file_name"] = None
        st.session_state["supplier_prepared_excel_bytes"] = None
        st.session_state["supplier_ignored_rows_df"] = None
        st.session_state["supplier_ignored_rows_file_name"] = None
        st.session_state["supplier_ignored_rows_excel_bytes"] = None
        st.session_state["supplier_compare_info_message"] = None
        _clear_supplier_result_state(st.session_state)
        st.session_state["supplier_ui_error"] = None
        update_progress(0.70, "Analyserar dubletter")

        if prepare_analysis.conflicts:
            # Render conflict resolution UI immediately after first build click.
            update_progress(1.0, "Klar")
            _rerun()

        update_progress(0.90, "Slutför byggning")
        ignored_rows_for_export_df = _build_ignored_rows_df(
            analysis=prepare_analysis,
            selected_candidates={},
        )
        prepared_df = _finalize_supplier_prepare_analysis(
            prepare_analysis,
            selected_candidates={},
        )
        _store_prepared_supplier_df(
            prepared_df=prepared_df,
            ignored_rows_df=ignored_rows_for_export_df,
            excluded_normalized_skus=prepare_analysis.excluded_normalized_skus,
            prepare_signature=current_prepare_signature,
            supplier_name=selected_supplier_name,
        )
        st.session_state["supplier_compare_info_message"] = _prepared_supplier_success_message(
            supplier_name=selected_supplier_name,
            exact_duplicate_rows_removed=prepare_analysis.exact_duplicate_rows_removed,
        )
        update_progress(1.0, "Klar")
        _rerun()
    except Exception as exc:
        _clear_supplier_prepare_state(st.session_state)
        _clear_supplier_result_state(st.session_state)
        st.session_state["supplier_ui_error"] = f"Kunde inte bygga om leverantörsfilen: {exc}"
    finally:
        clear_progress()


def handle_finalize_supplier_prepare(
    *,
    prepare_analysis: SupplierPrepareAnalysis,
    current_choices: dict[str, str],
    current_prepare_signature: str,
    selected_supplier_name: str,
) -> None:
    try:
        ignored_rows_for_export_df = _build_ignored_rows_df(
            analysis=prepare_analysis,
            selected_candidates=current_choices,
        )
        prepared_df = _finalize_supplier_prepare_analysis(
            prepare_analysis,
            selected_candidates=current_choices,
        )
        _store_prepared_supplier_df(
            prepared_df=prepared_df,
            ignored_rows_df=ignored_rows_for_export_df,
            excluded_normalized_skus=prepare_analysis.excluded_normalized_skus,
            prepare_signature=current_prepare_signature,
            supplier_name=selected_supplier_name,
        )
        _clear_supplier_result_state(st.session_state)
        st.session_state["supplier_ui_error"] = None
        st.session_state["supplier_compare_info_message"] = _prepared_supplier_success_message(
            supplier_name=selected_supplier_name,
            exact_duplicate_rows_removed=prepare_analysis.exact_duplicate_rows_removed,
        )
        _rerun()
    except Exception as exc:
        st.session_state["supplier_ui_error"] = (
            f"Kunde inte slutföra byggningen av leverantörsfilen: {exc}"
        )


def handle_run_supplier_compare(
    *,
    hicore_file: dict[str, object],
    selected_supplier_name: str,
    prepared_supplier_df: pd.DataFrame,
    excluded_brands: list[str],
    profile_excluded_normalized_skus: frozenset[str],
) -> None:
    update_progress, clear_progress = _build_progress_updater(label="Leverantörsjämförelse")
    update_progress(0.0, "Startar")
    try:
        result = _compute_supplier_result(
            hicore_file_name=str(hicore_file["name"]),  # type: ignore[index]
            hicore_bytes=hicore_file["bytes"],  # type: ignore[index]
            supplier_name=selected_supplier_name,
            supplier_df=prepared_supplier_df,
            excluded_brands=[str(name) for name in excluded_brands],
            profile_excluded_normalized_skus=set(profile_excluded_normalized_skus),
            progress_callback=update_progress,
        )
        update_progress(1.0, "Klar")
        st.session_state["supplier_ui_result"] = result
        st.session_state["supplier_ui_error"] = None
    except Exception as exc:
        st.session_state["supplier_ui_result"] = None
        st.session_state["supplier_ui_error"] = str(exc)
    finally:
        clear_progress()

