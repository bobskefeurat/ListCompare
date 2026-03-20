from __future__ import annotations

import streamlit as st

from .common import (
    MENU_COMPARE,
    MENU_SETTINGS,
    MENU_SUPPLIER,
)
from .io.index_names import _load_brands_from_index, _load_suppliers_from_index
from .pages.compare import _render_compare_page
from .pages.settings import _render_settings_page
from .pages.supplier import _render_supplier_page
from .runtime_paths import (
    brand_index_path as _brand_index_path,
    ensure_runtime_storage_initialized as _ensure_runtime_storage_initialized,
    supplier_index_path as _supplier_index_path,
)
from .session.bootstrap import init_session_state as _init_session_state
from .session.file_inputs import get_stored_file as _get_stored_file
from .session.shared_sync_status import store_shared_sync_status as _store_shared_sync_status
from .services.index_sync import (
    sync_index_options_from_uploaded_hicore as _sync_index_options_from_uploaded_hicore,
)
from .services.shared_sync import sync_shared_files as _sync_shared_files


def main() -> None:
    st.set_page_config(page_title="ListCompare", layout="wide")
    _ensure_runtime_storage_initialized()
    shared_sync_status = _sync_shared_files()
    _init_session_state(st.session_state)
    _store_shared_sync_status(
        st.session_state,
        level=shared_sync_status.level,
        message=shared_sync_status.message,
        profile_conflicts=shared_sync_status.profile_conflicts,
        source="Appstart",
    )

    st.title("ListCompare")
    st.sidebar.title("Meny")
    selected_menu = st.sidebar.radio(
        "Välj vy",
        options=[MENU_COMPARE, MENU_SUPPLIER, MENU_SETTINGS],
    )

    indexed_suppliers, supplier_index_error = _load_suppliers_from_index(_supplier_index_path())
    indexed_brands, brand_index_error = _load_brands_from_index(_brand_index_path())

    index_sync_result = _sync_index_options_from_uploaded_hicore(
        indexed_suppliers=indexed_suppliers,
        indexed_brands=indexed_brands,
        stored_hicore_file=_get_stored_file(st.session_state, kind="hicore"),
    )
    if index_sync_result.warning_message:
        st.warning(index_sync_result.warning_message)

    excluded_brands = [str(name) for name in st.session_state.get("excluded_brands", [])]
    if selected_menu == MENU_COMPARE:
        _render_compare_page(excluded_brands=excluded_brands)
    elif selected_menu == MENU_SUPPLIER:
        _render_supplier_page(
            supplier_options=index_sync_result.supplier_options,
            supplier_index_error=supplier_index_error,
            new_supplier_names=index_sync_result.new_supplier_names,
            excluded_brands=excluded_brands,
        )
    else:
        _render_settings_page(
            brand_options=index_sync_result.brand_options,
            brand_index_error=brand_index_error,
            new_brand_names=index_sync_result.new_brand_names,
            hicore_missing_brand_column=index_sync_result.hicore_missing_brand_column,
        )


if __name__ == "__main__":
    main()

