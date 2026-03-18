from __future__ import annotations

from typing import Optional

import streamlit as st

from ..common import MENU_SETTINGS
from ..runtime_paths import (
    brand_index_path as _brand_index_path,
    ui_settings_path as _ui_settings_path,
)
from ..session.file_inputs import get_stored_file as _get_stored_file
from ..session.run_state import clear_all_run_state as _clear_all_run_state
from ..session.settings_state import (
    persist_excluded_brands_setting as _persist_excluded_brands_setting,
)


def _render_settings_page(
    *,
    brand_options: list[str],
    brand_index_error: Optional[str],
    new_brand_names: list[str],
    hicore_missing_brand_column: bool,
) -> None:
    st.header(MENU_SETTINGS)
    brand_index_path = _brand_index_path()
    ui_settings_path = _ui_settings_path()

    current_hicore = _get_stored_file(st.session_state, kind="hicore")
    existing_excluded = [name for name in st.session_state["excluded_brands"] if name in brand_options]
    if existing_excluded != st.session_state["excluded_brands"]:
        st.session_state["excluded_brands"] = existing_excluded
        _persist_excluded_brands_setting(st.session_state, path=ui_settings_path)
        _clear_all_run_state(st.session_state)

    if "excluded_brands_widget" not in st.session_state:
        st.session_state["excluded_brands_widget"] = list(st.session_state["excluded_brands"])
    else:
        widget_selection = [
            name for name in st.session_state.get("excluded_brands_widget", []) if name in brand_options
        ]
        if widget_selection != st.session_state.get("excluded_brands_widget", []):
            st.session_state["excluded_brands_widget"] = widget_selection

    selected_excluded = st.multiselect(
        "Varumärken som ska exkluderas i körningar",
        options=brand_options,
        placeholder="Välj ett eller flera varumärken...",
        disabled=bool(current_hicore is not None and hicore_missing_brand_column),
        key="excluded_brands_widget",
    )
    normalized_selected = [name for name in selected_excluded if name in brand_options]
    if normalized_selected != st.session_state["excluded_brands"]:
        st.session_state["excluded_brands"] = normalized_selected
        _persist_excluded_brands_setting(st.session_state, path=ui_settings_path)
        _clear_all_run_state(st.session_state)

    st.caption(f"Antal varumärken: {len(brand_options)}")
    if new_brand_names:
        st.success(
            f"Uppdaterade {brand_index_path.name} med {len(new_brand_names)} ny(a) varumärke(n) från HiCore."
        )
    if brand_index_error:
        st.warning(f"Kunde inte läsa {brand_index_path.name} vid uppstart: {brand_index_error}")
    if st.session_state.get("ui_settings_load_error"):
        st.warning(
            f"Kunde inte läsa {ui_settings_path.name} vid uppstart: {st.session_state['ui_settings_load_error']}"
        )
    if st.session_state.get("ui_settings_save_error"):
        st.warning(
            f"Kunde inte spara {ui_settings_path.name}: {st.session_state['ui_settings_save_error']}"
        )
    if current_hicore is not None and hicore_missing_brand_column:
        st.warning(
            'HiCore-filen saknar kolumnen "Varumärke". Varumärkesexkludering är inte tillgänglig för den filen.'
        )
