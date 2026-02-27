from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from ..core.supplier_products import find_supplier_id_column
from .supplier_profile_utils import (
    SUPPLIER_HICORE_SKU_COLUMN,
    SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU,
    SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS,
    build_supplier_hicore_renamed_copy as _build_supplier_hicore_renamed_copy,
    matches_profile_output_format as _matches_profile_output_format,
    missing_profile_source_columns as _missing_profile_source_columns,
    normalize_supplier_transform_profile_options as _normalize_supplier_transform_profile_options,
    profile_has_required_sku_mapping as _profile_has_required_sku_mapping,
    rebuilt_supplier_file_name as _rebuilt_supplier_file_name,
)
from .ui.common import (
    FILE_STATE_KEYS,
    SUPPLIER_INDEX_PATH,
    SupplierUiResult,
)
from .ui.compute import _compute_supplier_result
from .ui.data_io import _df_excel_bytes, _read_supplier_upload
from .ui.state import (
    _clear_all_run_state,
    _clear_supplier_state,
    _get_supplier_transform_profile,
    _normalize_selected_supplier_for_options,
    _render_file_input,
    _request_supplier_profile_editor,
    _rerun,
    _sync_selected_supplier_between_views,
)
def _render_supplier_results(result: SupplierUiResult) -> None:
    if result.warning_message:
        st.warning(result.warning_message)

    st.metric("Internal only (supplier)", result.internal_only_count)
    st.download_button(
        label="Ladda ner internal_only_skus.csv",
        data=result.internal_only_csv_bytes,
        file_name="internal_only_skus.csv",
        mime="text/csv",
        key="download_internal_only_csv",
    )
    st.dataframe(result.internal_only_df, use_container_width=True)



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
        label="Leverant\u00f6rsfil (.csv/.xlsx/.xls/.xlsm)",
        file_types=["csv", "xlsx", "xls", "xlsm"],
        uploader_key="supplier_file_uploader",
    )
    info_message = st.session_state.get("supplier_compare_info_message")
    if info_message:
        st.success(str(info_message))
        st.session_state["supplier_compare_info_message"] = None

    previous_supplier_name = st.session_state.get("_last_supplier_internal_name")
    supplier_internal_name = st.selectbox(
        "V\u00e4lj leverant\u00f6r",
        options=supplier_options,
        index=None,
        placeholder="V\u00e4lj leverant\u00f6r...",
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

    profile_mapping, profile_options = _get_supplier_transform_profile(selected_supplier_name)
    profile_exists = bool(profile_mapping)
    profile_has_required_sku = _profile_has_required_sku_mapping(profile_mapping)
    profile_ready = profile_exists and profile_has_required_sku
    st.session_state["supplier_transform_attention_required"] = (
        selected_supplier_name != "" and not profile_ready
    )

    supplier_file_read_error: Optional[str] = None
    supplier_file_direct_compare_format = False
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
            try:
                find_supplier_id_column(df_supplier_uploaded)
                supplier_file_direct_compare_format = True
            except Exception:
                supplier_file_direct_compare_format = False

            if profile_ready:
                missing_profile_columns_for_file = _missing_profile_source_columns(
                    profile_mapping,
                    source_columns,
                )
                profile_matches_uploaded_file = len(missing_profile_columns_for_file) == 0
                file_matches_profile_output_format = _matches_profile_output_format(
                    profile_mapping,
                    source_columns,
                )
        except Exception as exc:
            supplier_file_read_error = str(exc)

    if selected_supplier_name == "":
        st.info("V\u00e4lj leverant\u00f6r f\u00f6r att kontrollera profilstatus.")
    elif not profile_exists:
        st.error(
            f'Saknar sparad leverant\u00f6rsprofil f\u00f6r "{selected_supplier_name}". '
            "Skapa en profil i fliken Leverantörsprofiler."
        )
    elif not profile_has_required_sku:
        st.error(
            f'Profilen f\u00f6r "{selected_supplier_name}" saknar mappning av "{SUPPLIER_HICORE_SKU_COLUMN}". '
            "SKU m\u00e5ste alltid vara matchad."
        )
    else:
        st.success(f'F\u00e4rdig leverant\u00f6rsprofil hittad f\u00f6r "{selected_supplier_name}".')

    if supplier_file is not None:
        if supplier_file_read_error is not None:
            st.error(f"Kunde inte l\u00e4sa leverant\u00f6rsfilen: {supplier_file_read_error}")
        elif profile_ready and file_matches_profile_output_format:
            st.success("Uppladdad leverant\u00f6rsfil matchar redan sparad profil i HiCore-format.")
        elif profile_ready and profile_matches_uploaded_file:
            st.info(
                "Leverant\u00f6rsfilen kan byggas om via profil. Tryck p\u00e5 \"Bygg om till Hicore-format\"."
            )
        elif profile_ready:
            st.warning(
                "Uppladdad leverant\u00f6rsfil matchar inte den sparade profilen. Saknade kolumner: "
                + ", ".join(missing_profile_columns_for_file)
            )

    can_run = (
        hicore_file is not None
        and supplier_file is not None
        and selected_supplier_name != ""
        and profile_ready
        and supplier_file_read_error is None
        and supplier_file_direct_compare_format
    )
    run_clicked = st.button(
        "K\u00f6r J\u00e4mf\u00f6relse",
        type="primary",
        disabled=not can_run,
        key="run_supplier_button",
    )

    can_rebuild_uploaded_file = (
        supplier_file is not None
        and selected_supplier_name != ""
        and profile_ready
        and supplier_file_read_error is None
        and profile_matches_uploaded_file
        and not file_matches_profile_output_format
        and df_supplier_uploaded is not None
    )
    can_manage_profile = selected_supplier_name != ""
    profile_action_label = (
        "Uppdatera leverant\u00f6rsprofil" if profile_exists else "Skapa leverant\u00f6rsprofil"
    )
    rebuild_col, profile_col = st.columns(2)
    if rebuild_col.button(
        "Bygg om till Hicore-format",
        type="secondary",
        disabled=not can_rebuild_uploaded_file,
        key="rebuild_supplier_file_with_profile_button",
    ):
        try:
            normalized_profile_options = _normalize_supplier_transform_profile_options(profile_options)
            rebuilt_df = _build_supplier_hicore_renamed_copy(
                df_supplier_uploaded,  # type: ignore[arg-type]
                target_to_source=profile_mapping,
                supplier_name=selected_supplier_name,
                strip_leading_zeros_from_sku=normalized_profile_options[
                    SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS
                ],
                ignore_rows_missing_sku=normalized_profile_options[
                    SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU
                ],
            )
            rebuilt_name = _rebuilt_supplier_file_name(selected_supplier_name)
            st.session_state[FILE_STATE_KEYS["supplier"]] = {
                "name": rebuilt_name,
                "bytes": _df_excel_bytes(rebuilt_df, sheet_name="HiCore-format"),
            }
            st.session_state["supplier_compare_info_message"] = (
                f'Leverant\u00f6rsfilen byggdes om med profilen f\u00f6r "{selected_supplier_name}" '
                "och ersatte tidigare uppladdad fil."
            )
            _clear_all_run_state()
            _rerun()
        except Exception as exc:
            st.session_state["supplier_ui_result"] = None
            st.session_state["supplier_ui_error"] = f"Kunde inte bygga om leverant\u00f6rsfilen: {exc}"
    if profile_col.button(
        profile_action_label,
        type="secondary",
        disabled=not can_manage_profile,
        key="update_supplier_profile_button",
    ):
        _request_supplier_profile_editor(selected_supplier_name)

    if run_clicked:
        try:
            result = _compute_supplier_result(
                hicore_bytes=hicore_file["bytes"],  # type: ignore[index]
                supplier_name=selected_supplier_name,
                supplier_file_name=str(supplier_file["name"]),  # type: ignore[index]
                supplier_bytes=supplier_file["bytes"],  # type: ignore[index]
                excluded_brands=[str(name) for name in excluded_brands],
            )
            st.session_state["supplier_ui_result"] = result
            st.session_state["supplier_ui_error"] = None
        except Exception as exc:
            st.session_state["supplier_ui_result"] = None
            st.session_state["supplier_ui_error"] = str(exc)

    st.caption(f"Antal leverant\u00f6rer: {len(supplier_options)}")
    if new_supplier_names:
        st.success(
            f"Uppdaterade {SUPPLIER_INDEX_PATH.name} med {len(new_supplier_names)} ny(a) leverant\u00f6r(er) fr\u00e5n HiCore."
        )
    if supplier_index_error:
        st.warning(
            f"Kunde inte l\u00e4sa {SUPPLIER_INDEX_PATH.name} vid uppstart: {supplier_index_error}"
        )

    if st.session_state["supplier_ui_error"]:
        st.error(st.session_state["supplier_ui_error"])
    if st.session_state["supplier_ui_result"] is not None:
        _render_supplier_results(st.session_state["supplier_ui_result"])

