from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from ....supplier_profile_utils import (
    filter_supplier_names as _filter_supplier_names,
    selected_dataframe_row_index as _selected_dataframe_row_index,
)
from ...state import _request_supplier_profile_editor, _split_suppliers_by_profile

def _render_supplier_profiles_overview(*, supplier_options: list[str]) -> None:
    st.subheader("Leverantörsprofiler")
    st.caption("Profilerna är ett fristående bibliotek. Välj leverantör för att öppna eller skapa profil.")

    search_query = st.text_input(
        "Sök leverantör",
        placeholder="Sök i båda listorna...",
        key="supplier_profiles_search_query",
    )
    suppliers_with_profile, suppliers_without_profile = _split_suppliers_by_profile(supplier_options)
    filtered_with_profile = _filter_supplier_names(suppliers_with_profile, search_query)
    filtered_without_profile = _filter_supplier_names(suppliers_without_profile, search_query)

    with_col, without_col = st.columns(2)

    with with_col:
        st.markdown(f"**Har profil ({len(filtered_with_profile)}/{len(suppliers_with_profile)})**")
        selected_with_profile: Optional[str] = None
        if filtered_with_profile:
            st.caption("Välj leverantör med profil")
            with st.container(height=320, border=True):
                with_profile_event = st.dataframe(
                    pd.DataFrame({"Leverantör": filtered_with_profile}),
                    hide_index=True,
                    use_container_width=True,
                    height=300,
                    key="supplier_profiles_with_profile_table",
                    on_select="rerun",
                    selection_mode="single-cell",
                )
            selected_idx = _selected_dataframe_row_index(with_profile_event)
            if selected_idx is not None:
                if 0 <= selected_idx < len(filtered_with_profile):
                    selected_with_profile = filtered_with_profile[selected_idx]
        else:
            st.caption("Inga leverantörer matchar sökningen.")

        if st.button(
            "\u00d6ppna profil",
            type="secondary",
            disabled=selected_with_profile is None,
            key="open_supplier_profile_from_overview_button",
        ):
            _request_supplier_profile_editor(str(selected_with_profile))

    with without_col:
        st.markdown(
            f"**Saknar profil ({len(filtered_without_profile)}/{len(suppliers_without_profile)})**"
        )
        selected_without_profile: Optional[str] = None
        if filtered_without_profile:
            st.caption("Välj leverantör utan profil")
            with st.container(height=320, border=True):
                without_profile_event = st.dataframe(
                    pd.DataFrame({"Leverantör": filtered_without_profile}),
                    hide_index=True,
                    use_container_width=True,
                    height=300,
                    key="supplier_profiles_without_profile_table",
                    on_select="rerun",
                    selection_mode="single-cell",
                )
            selected_idx = _selected_dataframe_row_index(without_profile_event)
            if selected_idx is not None:
                if 0 <= selected_idx < len(filtered_without_profile):
                    selected_without_profile = filtered_without_profile[selected_idx]
        else:
            st.caption("Inga leverantörer matchar sökningen.")

        if st.button(
            "Skapa profil",
            type="secondary",
            disabled=selected_without_profile is None,
            key="create_supplier_profile_from_overview_button",
        ):
            _request_supplier_profile_editor(str(selected_without_profile))

