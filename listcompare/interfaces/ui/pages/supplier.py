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
from ..session.supplier_page_state import (
    apply_requested_supplier_page_state as _apply_requested_supplier_page_state,
)
from ..session.supplier_selection import (
    sync_supplier_selection_session_state as _sync_supplier_selection_session_state,
)


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

    _sync_supplier_selection_session_state(
        st.session_state,
        supplier_options,
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
