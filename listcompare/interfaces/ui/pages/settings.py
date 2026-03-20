from __future__ import annotations

from typing import Optional

import streamlit as st

from ..common import MENU_SETTINGS
from ..persistence import profile_store as _profile_store
from ..runtime_paths import (
    brand_index_path as _brand_index_path,
    supplier_transform_profiles_path as _supplier_transform_profiles_path,
    ui_settings_path as _ui_settings_path,
)
from ..session.file_inputs import get_stored_file as _get_stored_file
from ..session.run_state import clear_all_run_state as _clear_all_run_state
from ..session.shared_sync_status import store_shared_sync_status as _store_shared_sync_status
from ..session.settings_state import (
    persist_excluded_brands_setting as _persist_excluded_brands_setting,
)
from ..services.shared_sync import (
    find_shared_sync_folder_candidates as _find_shared_sync_folder_candidates,
    save_configured_shared_folder as _save_configured_shared_folder,
    sync_shared_files as _sync_shared_files,
)
def _reload_profiles_after_shared_sync() -> None:
    supplier_profiles, supplier_profiles_error = _profile_store.load_profiles(
        _supplier_transform_profiles_path()
    )
    st.session_state["supplier_transform_profiles"] = dict(supplier_profiles)
    st.session_state["supplier_transform_profiles_load_error"] = supplier_profiles_error


def _run_shared_sync_and_refresh(*, source: str) -> None:
    sync_status = _sync_shared_files()
    _store_shared_sync_status(
        st.session_state,
        level=sync_status.level,
        message=sync_status.message,
        profile_conflicts=sync_status.profile_conflicts,
        source=source,
    )
    _reload_profiles_after_shared_sync()
    _clear_all_run_state(st.session_state)
    st.rerun()


def _render_shared_sync_settings() -> None:
    st.subheader("Delad synk")
    st.caption(
        "Peka ut den gemensamma Drive-mappen som ska dela leverantörsprofiler samt "
        "leverantörs- och varumärkesindex."
    )
    if "shared_sync_folder_widget" not in st.session_state:
        st.session_state["shared_sync_folder_widget"] = str(
            st.session_state.get("shared_sync_folder", "")
        )

    shared_sync_candidates = _find_shared_sync_folder_candidates()
    configured_shared_folder = str(st.session_state.get("shared_sync_folder", "")).strip()
    shared_sync_folder = configured_shared_folder
    show_save_button = False
    save_button_label = "Spara synkmapp"

    if len(shared_sync_candidates) == 1:
        shared_sync_folder = shared_sync_candidates[0]
        st.info(f"Drive-mapp hittad automatiskt: {shared_sync_folder}")
        if configured_shared_folder != shared_sync_folder:
            show_save_button = True
            save_button_label = "Använd hittad mapp"
    elif shared_sync_candidates:
        current_candidate = configured_shared_folder
        if current_candidate in shared_sync_candidates:
            candidate_index = shared_sync_candidates.index(current_candidate)
        else:
            candidate_index = 0
        shared_sync_folder = st.selectbox(
            "Hittade Drive-mappar",
            options=shared_sync_candidates,
            index=candidate_index,
            key="shared_sync_folder_candidate",
        )
        st.caption("Välj mappen i listan om du vill byta aktiv delad synkmapp.")
        show_save_button = True
        save_button_label = "Använd vald mapp"
    else:
        st.caption("Ingen vanlig ListCompareShared-mapp hittades automatiskt. Ange sökvägen manuellt.")
        shared_sync_folder = st.text_input(
            "Drive-mapp för delad appdata",
            key="shared_sync_folder_widget",
            placeholder=r"G:\Min enhet\ListCompareShared",
        ).strip()
        show_save_button = True

    sync_col, action_col = st.columns(2)
    if sync_col.button("Synka nu", key="run_shared_sync_now"):
        _run_shared_sync_and_refresh(source="Inställningar: synka nu")
    if show_save_button and action_col.button(save_button_label, key="save_shared_sync_folder"):
        save_error = _save_configured_shared_folder(shared_sync_folder)
        st.session_state["shared_sync_save_error"] = save_error
        if save_error is None:
            st.session_state["shared_sync_folder_widget"] = shared_sync_folder
            st.session_state["shared_sync_folder"] = shared_sync_folder
            _run_shared_sync_and_refresh(source="Inställningar: spara synkmapp")

    if st.session_state.get("shared_sync_load_error"):
        st.warning(
            "Kunde inte läsa shared_sync_config.json vid uppstart: "
            f"{st.session_state['shared_sync_load_error']}"
        )
    if st.session_state.get("shared_sync_save_error"):
        st.warning(f"Kunde inte spara shared_sync_config.json: {st.session_state['shared_sync_save_error']}")
    shared_sync_status_message = str(st.session_state.get("shared_sync_status_message") or "").strip()
    shared_sync_status_level = str(st.session_state.get("shared_sync_status_level") or "").strip()
    shared_sync_status_source = str(st.session_state.get("shared_sync_status_source") or "").strip()
    if shared_sync_status_message:
        if shared_sync_status_source:
            st.caption(f"Senaste delade synk: {shared_sync_status_source}")
        if shared_sync_status_level == "disabled":
            st.info(shared_sync_status_message)
        elif shared_sync_status_level in ("warning", "error"):
            st.warning(shared_sync_status_message)
        else:
            st.success(shared_sync_status_message)


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
    _render_shared_sync_settings()

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
