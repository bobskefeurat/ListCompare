from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from .supplier_prepare_utils import (
    SupplierDuplicateConflict,
    SupplierPrepareAnalysis,
    SUPPLIER_PREPARE_IGNORE_GROUP,
    build_supplier_prepare_analysis as _build_supplier_prepare_analysis,
    finalize_supplier_prepare_analysis as _finalize_supplier_prepare_analysis,
    supplier_prepare_signature as _supplier_prepare_signature,
)
from .supplier_profile_utils import (
    SUPPLIER_HICORE_SKU_COLUMN,
    matches_profile_output_format as _matches_profile_output_format,
    missing_profile_source_columns as _missing_profile_source_columns,
    profile_has_required_sku_mapping as _profile_has_required_sku_mapping,
    rebuilt_supplier_file_name as _rebuilt_supplier_file_name,
)
from .ui.common import SUPPLIER_INDEX_PATH, SupplierUiResult
from .ui.compute import _compute_supplier_result
from .ui.data_io import _df_excel_bytes, _read_supplier_upload, _style_stock_mismatch_df
from .ui.state import (
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


def _build_progress_updater(*, label: str):
    status_placeholder = st.empty()
    progress_placeholder = st.empty()
    progress_bar = progress_placeholder.progress(0)

    def _update(progress: float, message: str) -> None:
        clamped = max(0.0, min(1.0, float(progress)))
        percent = int(round(clamped * 100))
        status_text = str(message).strip()
        if status_text != "":
            status_placeholder.caption(f"{label}: {status_text} ({percent}%)")
        else:
            status_placeholder.caption(f"{label}: {percent}%")
        progress_bar.progress(percent)

    def _clear() -> None:
        status_placeholder.empty()
        progress_placeholder.empty()

    return _update, _clear


def _store_prepared_supplier_df(
    *,
    prepared_df: pd.DataFrame,
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

    candidate_rows = []
    option_labels: dict[str, str] = {}
    for candidate_index, candidate in enumerate(conflict.candidates, start=1):
        option_label = f"Alternativ {candidate_index}"
        option_labels[candidate.candidate_id] = option_label
        candidate_rows.append(
            {
                "Alternativ": option_label,
                **candidate.row_values,
            }
        )

    st.dataframe(pd.DataFrame(candidate_rows), use_container_width=True, hide_index=True)

    selection_key = f"supplier_prepare_choice_{prepare_signature}_{conflict.group_key}"
    ignore_key = f"supplier_prepare_ignore_{prepare_signature}_{conflict.group_key}"
    stored_choice = str(stored_choices.get(conflict.group_key, "")).strip()
    if selection_key not in st.session_state and stored_choice in option_labels:
        st.session_state[selection_key] = stored_choice
    if ignore_key not in st.session_state:
        st.session_state[ignore_key] = stored_choice == SUPPLIER_PREPARE_IGNORE_GROUP

    selection_col, ignore_col = st.columns([4, 1])
    ignore_active = bool(st.session_state.get(ignore_key, False))
    selected_candidate_id = selection_col.selectbox(
        f"Välj vilken rad som gäller för SKU {sku_text}",
        options=[candidate.candidate_id for candidate in conflict.candidates],
        index=None,
        placeholder="Välj rätt rad...",
        format_func=lambda candidate_id: option_labels.get(candidate_id, candidate_id),
        key=selection_key,
        disabled=ignore_active,
    )
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
    return selected_candidate_id


def _render_supplier_results(result: SupplierUiResult) -> None:
    if result.warning_message:
        st.warning(result.warning_message)

    metric_col_1, metric_col_2, metric_col_3, metric_col_4 = st.columns(4)
    metric_col_1.metric("Utgående", result.outgoing_count)
    metric_col_2.metric("Nyheter", result.new_products_count)
    metric_col_3.metric("Prisuppdatering, Ej i lager", result.price_updates_out_of_stock_count)
    metric_col_4.metric("Prisuppdatering, I lager", result.price_updates_in_stock_count)

    tab_outgoing, tab_new, tab_price_oos, tab_price_in = st.tabs(
        [
            "Utgående",
            "Nyheter",
            "Prisuppdatering, Ej i lager",
            "Prisuppdatering, I lager",
        ]
    )
    with tab_outgoing:
        st.download_button(
            label="Ladda ner Utgående.xlsx",
            data=result.outgoing_excel_bytes,
            file_name="Utgående.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_supplier_outgoing_excel",
        )
        st.dataframe(result.outgoing_df, use_container_width=True)
    with tab_new:
        new_products_df = result.new_products_df
        if "name" in new_products_df.columns and "Artikelnamn" not in new_products_df.columns:
            new_products_df = new_products_df.rename(columns={"name": "Artikelnamn"})
        st.download_button(
            label="Ladda ner Nyheter.xlsx",
            data=result.new_products_excel_bytes,
            file_name="Nyheter.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_supplier_news_excel",
        )
        st.dataframe(new_products_df, use_container_width=True)
    with tab_price_oos:
        st.download_button(
            label="Ladda ner Prisuppdatering, Ej i lager.xlsx",
            data=result.price_updates_out_of_stock_excel_bytes,
            file_name="Prisuppdatering, Ej i lager.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_supplier_price_oos_excel",
        )
        st.dataframe(
            _style_stock_mismatch_df(result.price_updates_out_of_stock_df),
            use_container_width=True,
        )
    with tab_price_in:
        st.download_button(
            label="Ladda ner Prisuppdatering, I lager.xlsx",
            data=result.price_updates_in_stock_excel_bytes,
            file_name="Prisuppdatering, I lager.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_supplier_price_in_excel",
        )
        st.dataframe(
            _style_stock_mismatch_df(result.price_updates_in_stock_df),
            use_container_width=True,
        )


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
        elif profile_ready and profile_matches_uploaded_file:
            st.info(
                "Leverantörsfilen kan byggas om via profilen. "
                "Dublettkontrollen körs när du bygger filen."
            )
        elif profile_ready:
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
            st.session_state["supplier_compare_info_message"] = None
            _clear_supplier_result_state()
            st.session_state["supplier_ui_error"] = None
            update_progress(0.70, "Analyserar dubletter")

            if not prepare_analysis.conflicts:
                update_progress(0.90, "Slutf\u00f6r byggning")
                prepared_df = _finalize_supplier_prepare_analysis(
                    prepare_analysis,
                    selected_candidates={},
                )
                _store_prepared_supplier_df(
                    prepared_df=prepared_df,
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
                prepared_df = _finalize_supplier_prepare_analysis(
                    prepare_analysis,
                    selected_candidates=current_choices,
                )
                _store_prepared_supplier_df(
                    prepared_df=prepared_df,
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
        _render_supplier_results(st.session_state["supplier_ui_result"])
