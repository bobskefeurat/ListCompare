from __future__ import annotations

from typing import Optional

import streamlit as st

from ...common import (
    SUPPLIER_INDEX_PATH,
    SUPPLIER_PROFILE_MODE_EDITOR,
    SUPPLIER_PROFILE_MODE_OVERVIEW,
    SUPPLIER_TRANSFORM_PROFILES_PATH,
)
from .editor import _render_supplier_profile_editor
from .overview import _render_supplier_profiles_overview


def _render_supplier_transform_tab(
    *,
    supplier_options: list[str],
    supplier_index_error: Optional[str],
) -> None:
    if not supplier_options:
        st.warning(
            f"Inga leverantörer hittades i {SUPPLIER_INDEX_PATH.name}. Lägg till leverantörer först."
        )
        return

    profile_mode = st.session_state.get("supplier_profiles_mode", SUPPLIER_PROFILE_MODE_OVERVIEW)
    if profile_mode not in (SUPPLIER_PROFILE_MODE_OVERVIEW, SUPPLIER_PROFILE_MODE_EDITOR):
        profile_mode = SUPPLIER_PROFILE_MODE_OVERVIEW
        st.session_state["supplier_profiles_mode"] = profile_mode

    if profile_mode == SUPPLIER_PROFILE_MODE_EDITOR:
        _render_supplier_profile_editor(
            supplier_options=supplier_options,
            supplier_index_error=supplier_index_error,
        )
        return

    if supplier_index_error:
        st.warning(
            f"Kunde inte läsa {SUPPLIER_INDEX_PATH.name} vid uppstart: {supplier_index_error}"
        )
    if st.session_state.get("supplier_transform_profiles_load_error"):
        st.warning(
            "Kunde inte läsa "
            f"{SUPPLIER_TRANSFORM_PROFILES_PATH.name} vid uppstart: "
            f"{st.session_state['supplier_transform_profiles_load_error']}"
        )
    if st.session_state.get("supplier_transform_profiles_save_error"):
        st.warning(
            f"Kunde inte spara {SUPPLIER_TRANSFORM_PROFILES_PATH.name}: "
            f"{st.session_state['supplier_transform_profiles_save_error']}"
        )
    _render_supplier_profiles_overview(supplier_options=supplier_options)

