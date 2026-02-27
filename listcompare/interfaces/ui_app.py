from __future__ import annotations

from typing import Optional

import streamlit as st

from .supplier_profile_utils import (
    # Re-exported for compatibility with existing tests/importers.
    build_supplier_hicore_renamed_copy as _build_supplier_hicore_renamed_copy,
    matches_profile_output_format as _matches_profile_output_format,
    missing_profile_source_columns as _missing_profile_source_columns,
    profile_has_required_sku_mapping as _profile_has_required_sku_mapping,
)
from .ui.common import (
    BRAND_INDEX_PATH,
    MENU_COMPARE,
    MENU_SETTINGS,
    MENU_SUPPLIER,
    SUPPLIER_INDEX_PATH,
    SUPPLIER_PAGE_VIEW_COMPARE,
    SUPPLIER_PAGE_VIEW_TRANSFORM,
    SUPPLIER_PROFILE_MODE_EDITOR,
    SUPPLIER_PROFILE_MODE_OVERVIEW,
    UI_SETTINGS_PATH,
    CompareUiResult,
)
from .ui.compute import _compute_compare_result
from .ui.data_io import (
    _load_brands_from_index,
    _load_names_from_uploaded_hicore,
    _load_suppliers_from_index,
    _merge_brand_lists,
    _merge_supplier_lists,
    _save_brands_to_index,
    _save_suppliers_to_index,
    _style_stock_mismatch_df,
)
from .ui.state import (
    _clear_all_run_state,
    _get_stored_file,
    _init_session_state,
    _normalize_selected_supplier_for_options,
    _persist_excluded_brands_setting,
    _render_file_input,
    _sync_supplier_selection_session_state,
)
from .ui_supplier_compare import _render_supplier_compare_tab
from .ui_supplier_profiles import _render_supplier_transform_tab

def _render_compare_results(result: CompareUiResult) -> None:
    if result.warning_message:
        st.warning(result.warning_message)

    col1, col2 = st.columns(2)
    col1.metric("Only in Magento", result.only_in_magento_count)
    col2.metric("Stock mismatches", result.stock_mismatch_count)

    download_col1, download_col2 = st.columns(2)
    download_col1.download_button(
        label="Ladda ner only_in_magento_skus.csv",
        data=result.only_in_magento_csv_bytes,
        file_name="only_in_magento_skus.csv",
        mime="text/csv",
        key="download_only_in_magento_csv",
    )
    download_col2.download_button(
        label="Ladda ner stock_mismatch_skus.csv",
        data=result.stock_mismatch_csv_bytes,
        file_name="stock_mismatch_skus.csv",
        mime="text/csv",
        key="download_stock_mismatch_csv",
    )

    tab1, tab2 = st.tabs(["Only in Magento", "Stock mismatches"])
    with tab1:
        st.dataframe(result.only_in_magento_df, use_container_width=True)
    with tab2:
        st.dataframe(_style_stock_mismatch_df(result.stock_mismatch_df), use_container_width=True)


def _render_compare_page(*, excluded_brands: list[str]) -> None:
    st.header(MENU_COMPARE)
    st.caption("Ladda upp filer.")

    hicore_file = _render_file_input(
        kind="hicore",
        label="HiCore-export (.csv)",
        file_types=["csv"],
        uploader_key="compare_hicore_uploader",
    )
    magento_file = _render_file_input(
        kind="magento",
        label="Magento-export (.csv)",
        file_types=["csv"],
        uploader_key="compare_magento_uploader",
    )

    if excluded_brands:
        shown_brands = excluded_brands[:8]
        extra_count = len(excluded_brands) - len(shown_brands)
        suffix = f" (+{extra_count} till)" if extra_count > 0 else ""
        st.info(
            f"Exkluderade varum\u00e4rken: {', '.join(shown_brands)}{suffix}."
        )
    else:
        st.caption("Inga varum\u00e4rken exkluderas. \u00c4ndra i Inst\u00e4llningar vid behov.")

    can_run = hicore_file is not None and magento_file is not None
    if st.button(
        "K\u00f6r J\u00e4mf\u00f6relse",
        type="primary",
        disabled=not can_run,
        key="run_compare_button",
    ):
        try:
            result = _compute_compare_result(
                hicore_bytes=hicore_file["bytes"],  # type: ignore[index]
                magento_bytes=magento_file["bytes"],  # type: ignore[index]
                excluded_brands=[str(name) for name in excluded_brands],
            )
            st.session_state["compare_ui_result"] = result
            st.session_state["compare_ui_error"] = None
        except Exception as exc:
            st.session_state["compare_ui_result"] = None
            st.session_state["compare_ui_error"] = str(exc)

    if st.session_state["compare_ui_error"]:
        st.error(st.session_state["compare_ui_error"])
    if st.session_state["compare_ui_result"] is not None:
        _render_compare_results(st.session_state["compare_ui_result"])


def _render_supplier_page(
    *,
    supplier_options: list[str],
    supplier_index_error: Optional[str],
    new_supplier_names: list[str],
    excluded_brands: list[str],
) -> None:
    st.header(MENU_SUPPLIER)
    valid_views = (SUPPLIER_PAGE_VIEW_COMPARE, SUPPLIER_PAGE_VIEW_TRANSFORM)

    requested_view = st.session_state.get("supplier_page_view_request")
    if requested_view in valid_views:
        st.session_state["supplier_page_view"] = requested_view
    st.session_state["supplier_page_view_request"] = None

    requested_profile_mode = st.session_state.get("supplier_profiles_mode_request")
    if requested_profile_mode in (SUPPLIER_PROFILE_MODE_OVERVIEW, SUPPLIER_PROFILE_MODE_EDITOR):
        st.session_state["supplier_profiles_mode"] = requested_profile_mode
    st.session_state["supplier_profiles_mode_request"] = None

    requested_profile_supplier = _normalize_selected_supplier_for_options(
        st.session_state.get("supplier_profiles_supplier_request"),
        supplier_options,
    )
    if requested_profile_supplier is not None:
        st.session_state["supplier_profiles_active_supplier"] = requested_profile_supplier
        st.session_state["supplier_internal_name"] = requested_profile_supplier
        st.session_state["supplier_transform_internal_name"] = requested_profile_supplier
    st.session_state["supplier_profiles_supplier_request"] = None

    if st.session_state.get("supplier_page_view") not in valid_views:
        st.session_state["supplier_page_view"] = SUPPLIER_PAGE_VIEW_COMPARE

    previous_rendered_view = st.session_state.get("supplier_page_view_last_rendered")
    current_view = st.session_state.get("supplier_page_view")
    if (
        current_view == SUPPLIER_PAGE_VIEW_TRANSFORM
        and previous_rendered_view != SUPPLIER_PAGE_VIEW_TRANSFORM
        and requested_profile_mode != SUPPLIER_PROFILE_MODE_EDITOR
    ):
        st.session_state["supplier_profiles_mode"] = SUPPLIER_PROFILE_MODE_OVERVIEW

    _sync_supplier_selection_session_state(supplier_options)

    attention_required = bool(st.session_state.get("supplier_transform_attention_required", False))
    if attention_required:
        st.markdown(
            """
<style>
@keyframes lc-transform-tab-blink {
  0%, 100% { background-color: #fff3cd; border-color: #ffcc00; }
  50% { background-color: #ffe08a; border-color: #ff9900; }
}
section.main div[data-testid="stRadio"] div[role="radiogroup"][aria-orientation="horizontal"] > label:nth-of-type(2) {
  animation: lc-transform-tab-blink 1s infinite;
  border: 1px solid #ffcc00;
  border-radius: 0.5rem;
}
</style>
            """,
            unsafe_allow_html=True,
        )
        st.warning("Saknad eller ofullständig profil. Gå till Leverantörsprofiler.")

    selected_view = st.radio(
        "Leverant\u00f6rsflik",
        options=list(valid_views),
        key="supplier_page_view",
        horizontal=True,
    )
    if selected_view == SUPPLIER_PAGE_VIEW_COMPARE:
        _render_supplier_compare_tab(
            supplier_options=supplier_options,
            supplier_index_error=supplier_index_error,
            new_supplier_names=new_supplier_names,
            excluded_brands=excluded_brands,
        )
    else:
        _render_supplier_transform_tab(
            supplier_options=supplier_options,
            supplier_index_error=supplier_index_error,
        )
    st.session_state["supplier_page_view_last_rendered"] = selected_view


def _render_settings_page(
    *,
    brand_options: list[str],
    brand_index_error: Optional[str],
    new_brand_names: list[str],
    hicore_missing_brand_column: bool,
) -> None:
    st.header(MENU_SETTINGS)

    current_hicore = _get_stored_file("hicore")
    existing_excluded = [name for name in st.session_state["excluded_brands"] if name in brand_options]
    if existing_excluded != st.session_state["excluded_brands"]:
        st.session_state["excluded_brands"] = existing_excluded
        _persist_excluded_brands_setting()
        _clear_all_run_state()

    if "excluded_brands_widget" not in st.session_state:
        st.session_state["excluded_brands_widget"] = list(st.session_state["excluded_brands"])
    else:
        widget_selection = [
            name for name in st.session_state.get("excluded_brands_widget", []) if name in brand_options
        ]
        if widget_selection != st.session_state.get("excluded_brands_widget", []):
            st.session_state["excluded_brands_widget"] = widget_selection

    selected_excluded = st.multiselect(
        "Varum\u00e4rken som ska exkluderas i k\u00f6rningar",
        options=brand_options,
        placeholder="V\u00e4lj ett eller flera varum\u00e4rken...",
        disabled=bool(current_hicore is not None and hicore_missing_brand_column),
        key="excluded_brands_widget",
    )
    normalized_selected = [name for name in selected_excluded if name in brand_options]
    if normalized_selected != st.session_state["excluded_brands"]:
        st.session_state["excluded_brands"] = normalized_selected
        _persist_excluded_brands_setting()
        _clear_all_run_state()

    st.caption(f"Antal varum\u00e4rken: {len(brand_options)}")
    if new_brand_names:
        st.success(
            f"Uppdaterade {BRAND_INDEX_PATH.name} med {len(new_brand_names)} ny(a) varum\u00e4rke(n) fr\u00e5n HiCore."
        )
    if brand_index_error:
        st.warning(f"Kunde inte l\u00e4sa {BRAND_INDEX_PATH.name} vid uppstart: {brand_index_error}")
    if st.session_state.get("ui_settings_load_error"):
        st.warning(
            f"Kunde inte l\u00e4sa {UI_SETTINGS_PATH.name} vid uppstart: {st.session_state['ui_settings_load_error']}"
        )
    if st.session_state.get("ui_settings_save_error"):
        st.warning(
            f"Kunde inte spara {UI_SETTINGS_PATH.name}: {st.session_state['ui_settings_save_error']}"
        )
    if current_hicore is not None and hicore_missing_brand_column:
        st.warning(
            'HiCore-filen saknar kolumnen "Varum\u00e4rke". Varum\u00e4rkesexkludering \u00e4r inte tillg\u00e4nglig f\u00f6r den filen.'
        )


def main() -> None:
    st.set_page_config(page_title="ListCompare", layout="wide")
    _init_session_state()

    st.title("ListCompare")
    st.sidebar.title("Meny")
    selected_menu = st.sidebar.radio(
        "V\u00e4lj vy",
        options=[MENU_COMPARE, MENU_SUPPLIER, MENU_SETTINGS],
    )

    indexed_suppliers, supplier_index_error = _load_suppliers_from_index(SUPPLIER_INDEX_PATH)
    indexed_brands, brand_index_error = _load_brands_from_index(BRAND_INDEX_PATH)

    supplier_options = indexed_suppliers
    brand_options = indexed_brands
    new_supplier_names: list[str] = []
    new_brand_names: list[str] = []
    hicore_missing_brand_column = False

    stored_hicore_file = _get_stored_file("hicore")
    if stored_hicore_file is not None:
        try:
            (
                uploaded_suppliers,
                uploaded_brands,
                _has_supplier_column,
                has_brand_column,
            ) = _load_names_from_uploaded_hicore(
                str(stored_hicore_file["name"]),
                stored_hicore_file["bytes"],  # type: ignore[index]
            )
            supplier_options, new_supplier_names = _merge_supplier_lists(
                supplier_options,
                uploaded_suppliers,
            )
            if new_supplier_names:
                _save_suppliers_to_index(SUPPLIER_INDEX_PATH, supplier_options)

            brand_options, new_brand_names = _merge_brand_lists(
                brand_options,
                uploaded_brands,
            )
            if new_brand_names:
                _save_brands_to_index(BRAND_INDEX_PATH, brand_options)

            hicore_missing_brand_column = not has_brand_column
        except Exception as exc:
            st.warning(
                f"Kunde inte l\u00e4sa leverant\u00f6rs-/varum\u00e4rkeslista fr\u00e5n uppladdad HiCore-fil: {exc}"
            )

    excluded_brands = [str(name) for name in st.session_state.get("excluded_brands", [])]
    if selected_menu == MENU_COMPARE:
        _render_compare_page(excluded_brands=excluded_brands)
    elif selected_menu == MENU_SUPPLIER:
        _render_supplier_page(
            supplier_options=supplier_options,
            supplier_index_error=supplier_index_error,
            new_supplier_names=new_supplier_names,
            excluded_brands=excluded_brands,
        )
    else:
        _render_settings_page(
            brand_options=brand_options,
            brand_index_error=brand_index_error,
            new_brand_names=new_brand_names,
            hicore_missing_brand_column=hicore_missing_brand_column,
        )


if __name__ == "__main__":
    main()
