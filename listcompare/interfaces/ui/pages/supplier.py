from __future__ import annotations

from typing import Optional

import streamlit as st

from ..common import (
    MENU_SUPPLIER,
    SUPPLIER_PAGE_VIEW_COMPARE,
    SUPPLIER_PAGE_VIEW_TRANSFORM,
)
from ..features.supplier_compare.page import _render_supplier_compare_tab
from ..features.supplier_profiles.page import _render_supplier_transform_tab
from ..io.index_names import _load_suppliers_from_index
from ..persistence import profile_store as _profile_store
from ..runtime_paths import (
    supplier_index_path as _supplier_index_path,
    supplier_transform_profiles_path as _supplier_transform_profiles_path,
)
from ..services.shared_sync import (
    PROFILES_FILE_NAME as _PROFILES_FILE_NAME,
    SUPPLIER_INDEX_FILE_NAME as _SUPPLIER_INDEX_FILE_NAME,
    sync_shared_files as _sync_shared_files,
)
from ..session.supplier_page_state import (
    apply_requested_supplier_page_state as _apply_requested_supplier_page_state,
)
from ..session.shared_sync_status import store_shared_sync_status as _store_shared_sync_status
from ..session.shared_sync_status import maybe_run_auto_shared_sync as _maybe_run_auto_shared_sync
from ..session.supplier_selection import (
    sync_supplier_selection_session_state as _sync_supplier_selection_session_state,
)


def _sync_supplier_profiles_on_view_entry(
    session_state: dict[str, object],
    *,
    selected_view: str,
    supplier_options: list[str],
    supplier_index_error: Optional[str],
) -> tuple[list[str], Optional[str], Optional[str]]:
    previous_rendered_view = session_state.get("supplier_page_view_last_rendered")
    if (
        selected_view != SUPPLIER_PAGE_VIEW_TRANSFORM
        or previous_rendered_view == SUPPLIER_PAGE_VIEW_TRANSFORM
    ):
        return supplier_options, supplier_index_error, None

    sync_status = _maybe_run_auto_shared_sync(
        session_state,
        sync_runner=_sync_shared_files,
        targets=(_SUPPLIER_INDEX_FILE_NAME, _PROFILES_FILE_NAME),
    )
    if sync_status is None:
        return supplier_options, supplier_index_error, None
    _store_shared_sync_status(
        session_state,
        level=sync_status.level,
        message=sync_status.message,
        profile_conflicts=sync_status.profile_conflicts,
        source="Leverantörer: öppna Leverantörsprofiler",
    )

    supplier_profiles, supplier_profiles_error = _profile_store.load_profiles(
        _supplier_transform_profiles_path()
    )
    session_state["supplier_transform_profiles"] = dict(supplier_profiles)
    session_state["supplier_transform_profiles_load_error"] = supplier_profiles_error

    refreshed_supplier_options, refreshed_supplier_index_error = _load_suppliers_from_index(
        _supplier_index_path()
    )
    if refreshed_supplier_index_error is None:
        supplier_options = refreshed_supplier_options
        supplier_index_error = None

    warning_message = None
    if sync_status.level in ("warning", "error"):
        warning_message = sync_status.message
    return supplier_options, supplier_index_error, warning_message


def _render_supplier_page(
    *,
    supplier_options: list[str],
    supplier_index_error: Optional[str],
    new_supplier_names: list[str],
    excluded_brands: list[str],
) -> None:
    st.header(MENU_SUPPLIER)
    valid_views = (SUPPLIER_PAGE_VIEW_COMPARE, SUPPLIER_PAGE_VIEW_TRANSFORM)
    _apply_requested_supplier_page_state(
        st.session_state,
        supplier_options=supplier_options,
    )

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
        "Leverantörsflik",
        options=list(valid_views),
        key="supplier_page_view",
        horizontal=True,
    )
    supplier_options, supplier_index_error, sync_warning_message = _sync_supplier_profiles_on_view_entry(
        st.session_state,
        selected_view=selected_view,
        supplier_options=supplier_options,
        supplier_index_error=supplier_index_error,
    )
    _sync_supplier_selection_session_state(
        st.session_state,
        supplier_options,
    )
    if sync_warning_message:
        st.warning(sync_warning_message)
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
