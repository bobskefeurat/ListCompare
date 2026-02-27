from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import streamlit as st

from ..supplier_profile_utils import (
    SUPPLIER_TRANSFORM_DEFAULT_OPTIONS,
    load_supplier_transform_profiles as _load_supplier_transform_profiles,
    normalize_supplier_transform_profile as _normalize_supplier_transform_profile,
    normalize_supplier_transform_profile_mapping as _normalize_supplier_transform_profile_mapping,
    normalize_supplier_transform_profile_options as _normalize_supplier_transform_profile_options,
    ordered_supplier_transform_profile_mapping as _ordered_supplier_transform_profile_mapping,
    save_supplier_transform_profiles as _save_supplier_transform_profiles,
)
from .common import (
    FILE_STATE_KEYS,
    SUPPLIER_PAGE_VIEW_COMPARE,
    SUPPLIER_PAGE_VIEW_TRANSFORM,
    SUPPLIER_PROFILE_MODE_EDITOR,
    SUPPLIER_PROFILE_MODE_OVERVIEW,
    SUPPLIER_TRANSFORM_PROFILES_PATH,
    UI_SETTINGS_PATH,
    UPLOADER_KEYS_BY_KIND,
)
from .data_io import _normalize_supplier_names
def _get_supplier_transform_profile(
    supplier_name: str,
) -> tuple[dict[str, str], dict[str, bool]]:
    normalized_supplier_name = str(supplier_name).strip()
    if normalized_supplier_name == "":
        return {}, dict(SUPPLIER_TRANSFORM_DEFAULT_OPTIONS)
    raw_profiles = st.session_state.get("supplier_transform_profiles", {})
    if not isinstance(raw_profiles, dict):
        return {}, dict(SUPPLIER_TRANSFORM_DEFAULT_OPTIONS)
    raw_profile = raw_profiles.get(normalized_supplier_name, {})
    if not isinstance(raw_profile, dict):
        return {}, dict(SUPPLIER_TRANSFORM_DEFAULT_OPTIONS)
    return _normalize_supplier_transform_profile(raw_profile)


def _normalize_selected_supplier_for_options(
    selected_supplier: object,
    supplier_options: list[str],
) -> Optional[str]:
    if selected_supplier is None:
        return None
    selected = str(selected_supplier).strip()
    if selected == "":
        return None
    return selected if selected in supplier_options else None


def _sync_selected_supplier_between_views(
    selected_supplier: Optional[str],
    supplier_options: list[str],
    *,
    target_key: str,
) -> None:
    normalized = _normalize_selected_supplier_for_options(selected_supplier, supplier_options)
    if st.session_state.get(target_key) != normalized:
        st.session_state[target_key] = normalized
    st.session_state["_last_supplier_internal_name"] = normalized


def _sync_supplier_selection_session_state(supplier_options: list[str]) -> None:
    normalized_compare_supplier = _normalize_selected_supplier_for_options(
        st.session_state.get("supplier_internal_name"),
        supplier_options,
    )
    canonical_supplier = normalized_compare_supplier
    if st.session_state.get("supplier_internal_name") != canonical_supplier:
        st.session_state["supplier_internal_name"] = canonical_supplier
    if st.session_state.get("supplier_transform_internal_name") != canonical_supplier:
        st.session_state["supplier_transform_internal_name"] = canonical_supplier
    st.session_state["_last_supplier_internal_name"] = canonical_supplier


def _supplier_has_saved_profile(supplier_name: str) -> bool:
    mapping, _ = _get_supplier_transform_profile(supplier_name)
    return bool(mapping)


def _split_suppliers_by_profile(supplier_options: list[str]) -> tuple[list[str], list[str]]:
    suppliers_with_profile: list[str] = []
    suppliers_without_profile: list[str] = []
    for supplier_name in supplier_options:
        if _supplier_has_saved_profile(supplier_name):
            suppliers_with_profile.append(supplier_name)
        else:
            suppliers_without_profile.append(supplier_name)
    return suppliers_with_profile, suppliers_without_profile


def _load_ui_settings(path: Path) -> tuple[dict[str, list[str]], Optional[str]]:
    default_settings: dict[str, list[str]] = {"excluded_brands": []}
    if not path.exists():
        return default_settings, None

    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, dict):
            raise ValueError("ui_settings.json m\u00e5ste inneh\u00e5lla ett JSON-objekt.")

        raw_excluded = raw.get("excluded_brands", [])
        if not isinstance(raw_excluded, list):
            raise ValueError('F\u00e4ltet "excluded_brands" m\u00e5ste vara en lista.')

        excluded_brands = _normalize_supplier_names([str(name) for name in raw_excluded])
        return {"excluded_brands": excluded_brands}, None
    except Exception as exc:
        return default_settings, str(exc)


def _save_ui_settings(path: Path, *, excluded_brands: list[str]) -> Optional[str]:
    payload = {
        "excluded_brands": _normalize_supplier_names([str(name) for name in excluded_brands]),
    }
    try:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return None
    except Exception as exc:
        return str(exc)


def _init_session_state() -> None:
    ui_settings, ui_settings_error = _load_ui_settings(UI_SETTINGS_PATH)
    supplier_transform_profiles, supplier_transform_profiles_error = _load_supplier_transform_profiles(
        SUPPLIER_TRANSFORM_PROFILES_PATH
    )
    defaults = {
        FILE_STATE_KEYS["hicore"]: None,
        FILE_STATE_KEYS["magento"]: None,
        FILE_STATE_KEYS["supplier"]: None,
        "compare_ui_result": None,
        "compare_ui_error": None,
        "supplier_ui_result": None,
        "supplier_ui_error": None,
        "excluded_brands": list(ui_settings.get("excluded_brands", [])),
        "supplier_internal_name": None,
        "supplier_transform_internal_name": None,
        "_last_supplier_internal_name": None,
        "ui_settings_load_error": ui_settings_error,
        "ui_settings_save_error": None,
        "supplier_transform_profiles": dict(supplier_transform_profiles),
        "supplier_transform_profiles_load_error": supplier_transform_profiles_error,
        "supplier_transform_profiles_save_error": None,
        "supplier_page_view": SUPPLIER_PAGE_VIEW_COMPARE,
        "supplier_page_view_last_rendered": SUPPLIER_PAGE_VIEW_COMPARE,
        "supplier_page_view_request": None,
        "supplier_profiles_mode": SUPPLIER_PROFILE_MODE_OVERVIEW,
        "supplier_profiles_mode_request": None,
        "supplier_profiles_supplier_request": None,
        "supplier_profiles_active_supplier": None,
        "supplier_profiles_search_query": "",
        "supplier_profiles_delete_confirm": False,
        "supplier_transform_attention_required": False,
        "supplier_compare_info_message": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _clear_compare_state() -> None:
    st.session_state["compare_ui_result"] = None
    st.session_state["compare_ui_error"] = None


def _clear_supplier_state() -> None:
    st.session_state["supplier_ui_result"] = None
    st.session_state["supplier_ui_error"] = None


def _clear_all_run_state() -> None:
    _clear_compare_state()
    _clear_supplier_state()


def _persist_excluded_brands_setting() -> None:
    save_error = _save_ui_settings(
        UI_SETTINGS_PATH,
        excluded_brands=[str(name) for name in st.session_state.get("excluded_brands", [])],
    )
    st.session_state["ui_settings_save_error"] = save_error
    if save_error is None:
        st.session_state["ui_settings_load_error"] = None


def _persist_supplier_transform_profile(
    *,
    supplier_name: str,
    target_to_source: dict[str, str],
    options: dict[str, bool],
) -> Optional[str]:
    normalized_supplier_name = str(supplier_name).strip()
    if normalized_supplier_name == "":
        return "Kan inte spara profil utan leverant\u00f6rsnamn."

    profiles: dict[str, dict[str, object]] = {}
    for name, raw_profile in st.session_state.get("supplier_transform_profiles", {}).items():
        if not isinstance(name, str) or not isinstance(raw_profile, dict):
            continue
        mapping, normalized_options = _normalize_supplier_transform_profile(raw_profile)
        if not mapping:
            continue
        profiles[name] = {
            "target_to_source": _ordered_supplier_transform_profile_mapping(mapping),
            "options": normalized_options,
        }

    profiles[normalized_supplier_name] = {
        "target_to_source": _ordered_supplier_transform_profile_mapping(
            _normalize_supplier_transform_profile_mapping(target_to_source)
        ),
        "options": _normalize_supplier_transform_profile_options(options),
    }

    save_error = _save_supplier_transform_profiles(
        SUPPLIER_TRANSFORM_PROFILES_PATH,
        profiles=profiles,
    )
    st.session_state["supplier_transform_profiles_save_error"] = save_error
    if save_error is None:
        st.session_state["supplier_transform_profiles"] = profiles
        st.session_state["supplier_transform_profiles_load_error"] = None
    return save_error


def _delete_supplier_transform_profile(*, supplier_name: str) -> Optional[str]:
    normalized_supplier_name = str(supplier_name).strip()
    if normalized_supplier_name == "":
        return "Kan inte ta bort profil utan leverant\u00f6rsnamn."

    profiles: dict[str, dict[str, object]] = {}
    for name, raw_profile in st.session_state.get("supplier_transform_profiles", {}).items():
        if not isinstance(name, str) or not isinstance(raw_profile, dict):
            continue
        if name.strip().casefold() == normalized_supplier_name.casefold():
            continue
        mapping, normalized_options = _normalize_supplier_transform_profile(raw_profile)
        if not mapping:
            continue
        profiles[name] = {
            "target_to_source": _ordered_supplier_transform_profile_mapping(mapping),
            "options": normalized_options,
        }

    save_error = _save_supplier_transform_profiles(
        SUPPLIER_TRANSFORM_PROFILES_PATH,
        profiles=profiles,
    )
    st.session_state["supplier_transform_profiles_save_error"] = save_error
    if save_error is None:
        st.session_state["supplier_transform_profiles"] = profiles
        st.session_state["supplier_transform_profiles_load_error"] = None
    return save_error


def _get_stored_file(kind: str) -> Optional[dict[str, object]]:
    return st.session_state.get(FILE_STATE_KEYS[kind])


def _store_uploaded_file(kind: str, uploaded_file) -> None:
    st.session_state[FILE_STATE_KEYS[kind]] = {
        "name": uploaded_file.name,
        "bytes": uploaded_file.getvalue(),
    }
    _clear_all_run_state()


def _clear_stored_file(kind: str) -> None:
    st.session_state[FILE_STATE_KEYS[kind]] = None
    for widget_key in UPLOADER_KEYS_BY_KIND.get(kind, ()):
        st.session_state.pop(widget_key, None)
    _clear_all_run_state()


def _rerun() -> None:
    rerun_fn = getattr(st, "rerun", None)
    if callable(rerun_fn):
        rerun_fn()
        return
    st.experimental_rerun()


def _request_supplier_profile_editor(supplier_name: str) -> None:
    normalized_supplier_name = str(supplier_name).strip()
    if normalized_supplier_name == "":
        return
    st.session_state["supplier_page_view_request"] = SUPPLIER_PAGE_VIEW_TRANSFORM
    st.session_state["supplier_profiles_mode_request"] = SUPPLIER_PROFILE_MODE_EDITOR
    st.session_state["supplier_profiles_supplier_request"] = normalized_supplier_name
    _rerun()


def _render_file_input(
    *,
    kind: str,
    label: str,
    file_types: list[str],
    uploader_key: str,
) -> Optional[dict[str, object]]:
    stored = _get_stored_file(kind)
    if stored is not None:
        filename = str(stored.get("name", ""))
        info_col, button_col = st.columns([5, 1])
        info_col.success(f"{label}: uppladdad ({filename})")
        if button_col.button("Byt fil", key=f"replace_{kind}_{uploader_key}"):
            _clear_stored_file(kind)
            _rerun()
        return stored

    uploaded = st.file_uploader(
        label,
        type=file_types,
        accept_multiple_files=False,
        key=uploader_key,
    )
    if uploaded is not None:
        _store_uploaded_file(kind, uploaded)
        _rerun()
    return None


