from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from ....supplier_prepare_utils import (
    SupplierPrepareAnalysis,
    build_supplier_prepare_analysis as _build_supplier_prepare_analysis,
    finalize_supplier_prepare_analysis as _finalize_supplier_prepare_analysis,
    supplier_prepare_signature as _supplier_prepare_signature,
)
from ....supplier_profile_utils import (
    SUPPLIER_HICORE_SKU_COLUMN,
    matches_profile_output_format as _matches_profile_output_format,
    missing_profile_source_columns as _missing_profile_source_columns,
    profile_has_required_sku_mapping as _profile_has_required_sku_mapping,
)
from ...common import SUPPLIER_INDEX_PATH
from ...compute_supplier import _compute_supplier_result
from ...data_io import _read_supplier_upload
from ...shared.presentation import (
    build_progress_updater as _build_progress_updater,
    with_one_based_index as _with_one_based_index,
)
from ...state import (
    _clear_supplier_prepare_state,
    _clear_supplier_result_state,
    _clear_supplier_state,
    _get_supplier_transform_profile_details,
    _normalize_selected_supplier_for_options,
    _render_file_input,
    _request_supplier_profile_editor,
    _rerun,
    _sync_selected_supplier_between_views,
)
from .prepare import (
    _build_ignored_rows_df,
    _prepared_supplier_success_message,
    _render_prepare_conflict_group,
    _store_prepared_supplier_df,
    _sync_supplier_prepare_state,
)
from .results import _render_supplier_results

def _render_supplier_compare_tab(
    *,
    supplier_options: list[str],
    supplier_index_error: Optional[str],
    new_supplier_names: list[str],
    excluded_brands: list[str],
) -> None:
    normalized_compare_supplier = _normalize_selected_supplier_for_options(
        st.session_state.get("supplier_internal_name"),
        supplier_options,
    )
    if st.session_state.get("supplier_internal_name") != normalized_compare_supplier:
        st.session_state["supplier_internal_name"] = normalized_compare_supplier

    hicore_file = _render_file_input(
        kind="hicore",
        label="HiCore-export (.csv)",
        file_types=["csv"],
        uploader_key="supplier_hicore_uploader",
    )
    supplier_file = _render_file_input(
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
        _clear_supplier_state()
    selected_supplier_name = (
        str(supplier_internal_name).strip() if supplier_internal_name is not None else ""
    )
    if st.session_state.get("supplier_profiles_active_supplier") != (
        selected_supplier_name if selected_supplier_name != "" else None
    ):
        st.session_state["supplier_profiles_active_supplier"] = (
            selected_supplier_name if selected_supplier_name != "" else None
        )
    _sync_selected_supplier_between_views(
        selected_supplier_name if selected_supplier_name != "" else None,
        supplier_options,
        target_key="supplier_transform_internal_name",
    )

    profile_mapping, profile_composite_fields, profile_filters, profile_options = (
        _get_supplier_transform_profile_details(selected_supplier_name)
    )
    profile_exists = bool(profile_mapping)
    profile_has_required_sku = _profile_has_required_sku_mapping(profile_mapping)
    profile_ready = profile_exists and profile_has_required_sku
    st.session_state["supplier_transform_attention_required"] = (
        selected_supplier_name != "" and not profile_ready
    )

    supplier_file_read_error: Optional[str] = None
    profile_matches_uploaded_file = False
    file_matches_profile_output_format = False
    missing_profile_columns_for_file: list[str] = []
    df_supplier_uploaded: Optional[pd.DataFrame] = None
    if supplier_file is not None:
        supplier_file_name = str(supplier_file["name"])  # type: ignore[index]
        supplier_bytes = supplier_file["bytes"]  # type: ignore[index]
        try:
            df_supplier_uploaded = _read_supplier_upload(supplier_file_name, supplier_bytes)
            source_columns = [str(column).strip() for column in df_supplier_uploaded.columns]
            if profile_ready:
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
        except Exception as exc:
            supplier_file_read_error = str(exc)

    current_prepare_signature: Optional[str] = None
    if (
        supplier_file is not None
        and selected_supplier_name != ""
        and profile_ready
        and supplier_file_read_error is None
    ):
        current_prepare_signature = _supplier_prepare_signature(
            supplier_name=selected_supplier_name,
            supplier_file_name=str(supplier_file["name"]),  # type: ignore[index]
            supplier_bytes=supplier_file["bytes"],  # type: ignore[index]
            profile_mapping=profile_mapping,
            profile_composite_fields=profile_composite_fields,
            profile_filters=profile_filters,
            profile_options=profile_options,
        )
    _sync_supplier_prepare_state(current_prepare_signature)

    stored_prepare_signature = st.session_state.get("supplier_prepared_signature")
    prepared_supplier_df = st.session_state.get("supplier_prepared_df")
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
    has_prepared_supplier_df = (
        current_prepare_signature is not None
        and stored_prepare_signature == current_prepare_signature
        and isinstance(prepared_supplier_df, pd.DataFrame)
    )
    has_pending_conflicts = (
        current_prepare_signature is not None
        and stored_prepare_signature == current_prepare_signature
        and prepare_analysis is not None
        and bool(prepare_analysis.conflicts)
    )

    if selected_supplier_name == "":
        st.info("Välj leverantör för att kontrollera profilstatus.")
    elif not profile_exists:
        st.error(
            f'Saknar sparad leverantörsprofil för "{selected_supplier_name}". '
            "Skapa en profil i fliken Leverantörsprofiler."
        )
    elif not profile_has_required_sku:
        st.error(
            f'Profilen för "{selected_supplier_name}" saknar mappning av "{SUPPLIER_HICORE_SKU_COLUMN}". '
            "SKU måste alltid vara matchad."
        )
    else:
        st.success(f'Färdig leverantörsprofil hittad för "{selected_supplier_name}".')

    if supplier_file is not None:
        if supplier_file_read_error is not None:
            st.error(f"Kunde inte läsa leverantörsfilen: {supplier_file_read_error}")
        elif profile_ready and file_matches_profile_output_format:
            st.info(
                "Uppladdad leverantörsfil matchar redan HiCore-formatet. "
                "Byggsteget kör ändå dublettkontrollen innan jämförelse."
            )
        elif profile_ready and not profile_matches_uploaded_file:
            st.warning(
                "Uppladdad leverantörsfil matchar inte den sparade profilen. Saknade kolumner: "
                + ", ".join(missing_profile_columns_for_file)
            )

    can_prepare_uploaded_file = (
        supplier_file is not None
        and selected_supplier_name != ""
        and profile_ready
        and supplier_file_read_error is None
        and (file_matches_profile_output_format or profile_matches_uploaded_file)
        and df_supplier_uploaded is not None
    )
    can_run = (
        hicore_file is not None
        and supplier_file is not None
        and selected_supplier_name != ""
        and has_prepared_supplier_df
    )
    can_manage_profile = selected_supplier_name != ""
    profile_action_label = (
        "Uppdatera leverantörsprofil" if profile_exists else "Skapa leverantörsprofil"
    )

    rebuild_col, profile_col = st.columns(2)
    if rebuild_col.button(
        "Bygg om till Hicore-format",
        type="secondary",
        disabled=not can_prepare_uploaded_file,
        key="rebuild_supplier_file_with_profile_button",
    ):
        update_progress, clear_progress = _build_progress_updater(
            label="Bygg om leverant\u00f6rsfil"
        )
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
            st.session_state["supplier_prepared_file_name"] = None
            st.session_state["supplier_prepared_excel_bytes"] = None
            st.session_state["supplier_ignored_rows_df"] = None
            st.session_state["supplier_ignored_rows_file_name"] = None
            st.session_state["supplier_ignored_rows_excel_bytes"] = None
            st.session_state["supplier_compare_info_message"] = None
            _clear_supplier_result_state()
            st.session_state["supplier_ui_error"] = None
            update_progress(0.70, "Analyserar dubletter")

            if not prepare_analysis.conflicts:
                update_progress(0.90, "Slutf\u00f6r byggning")
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
            _clear_supplier_prepare_state()
            _clear_supplier_result_state()
            st.session_state["supplier_ui_error"] = f"Kunde inte bygga om leverantörsfilen: {exc}"
        finally:
            clear_progress()

    if profile_col.button(
        profile_action_label,
        type="secondary",
        disabled=not can_manage_profile,
        key="update_supplier_profile_button",
    ):
        _request_supplier_profile_editor(selected_supplier_name)

    if (
        hicore_file is not None
        and supplier_file is not None
        and profile_ready
        and can_prepare_uploaded_file
        and not has_prepared_supplier_df
        and not has_pending_conflicts
    ):
        st.info('Bygg om till Hicore-format innan du kör jämförelsen.')

    if has_pending_conflicts and prepare_analysis is not None and current_prepare_signature is not None:
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
        all_conflicts_resolved = all(
            conflict.group_key in current_choices for conflict in prepare_analysis.conflicts
        )
        if st.button(
            "Slutför byggning",
            type="primary",
            disabled=not all_conflicts_resolved,
            key="finalize_supplier_prepare_button",
        ):
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
                    prepare_signature=current_prepare_signature,
                    supplier_name=selected_supplier_name,
                )
                _clear_supplier_result_state()
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

    if has_prepared_supplier_df:
        st.success("Den ombyggda leverantörsfilen är klar för jämförelse.")
        if isinstance(prepared_excel_bytes, bytes) and str(prepared_file_name).strip() != "":
            st.download_button(
                label="Ladda ner ombyggd leverantörsfil (Excel)",
                data=prepared_excel_bytes,
                file_name=str(prepared_file_name),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_prepared_supplier_excel",
            )
        if (
            isinstance(ignored_rows_excel_bytes, bytes)
            and str(ignored_rows_file_name).strip() != ""
            and isinstance(ignored_rows_df, pd.DataFrame)
            and not ignored_rows_df.empty
        ):
            st.caption(f"Ignorerade rader: {len(ignored_rows_df)}")
            st.download_button(
                label="Ladda ner ignorerade rader (Excel)",
                data=ignored_rows_excel_bytes,
                file_name=str(ignored_rows_file_name),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_supplier_ignored_rows_excel",
            )
            with st.expander("Visa ignorerade rader"):
                st.dataframe(_with_one_based_index(ignored_rows_df), use_container_width=True)

    run_clicked = st.button(
        "Kör Jämförelse",
        type="primary",
        disabled=not can_run,
        key="run_supplier_button",
    )

    if run_clicked:
        update_progress, clear_progress = _build_progress_updater(
            label="Leverant\u00f6rsj\u00e4mf\u00f6relse"
        )
        update_progress(0.0, "Startar")
        try:
            result = _compute_supplier_result(
                hicore_bytes=hicore_file["bytes"],  # type: ignore[index]
                supplier_name=selected_supplier_name,
                supplier_df=prepared_supplier_df,  # type: ignore[arg-type]
                excluded_brands=[str(name) for name in excluded_brands],
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

    st.caption(f"Antal leverantörer: {len(supplier_options)}")
    if new_supplier_names:
        st.success(
            f"Uppdaterade {SUPPLIER_INDEX_PATH.name} med {len(new_supplier_names)} ny(a) leverantör(er) från HiCore."
        )
    if supplier_index_error:
        st.warning(
            f"Kunde inte läsa {SUPPLIER_INDEX_PATH.name} vid uppstart: {supplier_index_error}"
        )

    if st.session_state["supplier_ui_error"]:
        st.error(st.session_state["supplier_ui_error"])
    if st.session_state["supplier_ui_result"] is not None:
        _render_supplier_results(
            st.session_state["supplier_ui_result"],
            supplier_name=selected_supplier_name,
        )

