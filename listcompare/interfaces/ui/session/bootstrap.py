from __future__ import annotations

from ..common import (
    COMPARE_PAGE_MODE_PRODUCTS,
    FILE_STATE_KEYS,
    SUPPLIER_PAGE_VIEW_COMPARE,
    SUPPLIER_PROFILE_MODE_OVERVIEW,
)
from ..persistence import shared_sync_store as _shared_sync_store
from ..persistence import profile_store as _profile_store
from ..runtime_paths import (
    shared_sync_config_path as _shared_sync_config_path,
    supplier_transform_profiles_path as _supplier_transform_profiles_path,
    ui_settings_path as _ui_settings_path,
)
from .settings_state import load_ui_settings


def init_session_state(session_state: dict[str, object]) -> None:
    ui_settings, ui_settings_error = load_ui_settings(_ui_settings_path())
    shared_sync_config, shared_sync_config_error = _shared_sync_store.load_shared_sync_config(
        _shared_sync_config_path()
    )
    supplier_transform_profiles, supplier_transform_profiles_error = _profile_store.load_profiles(
        _supplier_transform_profiles_path()
    )

    defaults: dict[str, object] = {
        FILE_STATE_KEYS["hicore"]: None,
        FILE_STATE_KEYS["magento"]: None,
        FILE_STATE_KEYS["compare_web_orders_hicore"]: None,
        FILE_STATE_KEYS["compare_web_orders_magento"]: None,
        FILE_STATE_KEYS["supplier"]: None,
        "compare_ui_result": None,
        "compare_ui_error": None,
        "web_order_compare_ui_result": None,
        "web_order_compare_ui_error": None,
        "compare_page_mode": COMPARE_PAGE_MODE_PRODUCTS,
        "supplier_ui_result": None,
        "supplier_ui_error": None,
        "supplier_prepared_df": None,
        "supplier_prepared_signature": None,
        "supplier_prepared_excluded_normalized_skus": frozenset(),
        "supplier_prepared_file_name": None,
        "supplier_prepared_excel_bytes": None,
        "supplier_ignored_rows_df": None,
        "supplier_ignored_rows_file_name": None,
        "supplier_ignored_rows_excel_bytes": None,
        "supplier_prepare_analysis": None,
        "supplier_prepare_resolution_choices": {},
        "excluded_brands": list(ui_settings.get("excluded_brands", [])),
        "supplier_internal_name": None,
        "_last_supplier_internal_name": None,
        "ui_settings_load_error": ui_settings_error,
        "ui_settings_save_error": None,
        "shared_sync_folder": str(shared_sync_config.get("shared_folder", "")).strip(),
        "shared_sync_load_error": shared_sync_config_error,
        "shared_sync_save_error": None,
        "shared_sync_status_level": "disabled",
        "shared_sync_status_message": None,
        "shared_sync_profile_conflicts": (),
        "shared_sync_status_source": None,
        "_auto_shared_sync_cache": {},
        "supplier_transform_profiles": dict(supplier_transform_profiles),
        "supplier_transform_profiles_load_error": supplier_transform_profiles_error,
        "supplier_transform_profiles_save_error": None,
        "supplier_page_view": SUPPLIER_PAGE_VIEW_COMPARE,
        "supplier_page_view_last_rendered": SUPPLIER_PAGE_VIEW_COMPARE,
        "supplier_page_view_request": None,
        "supplier_profiles_mode": SUPPLIER_PROFILE_MODE_OVERVIEW,
        "supplier_profiles_mode_request": None,
        "supplier_profiles_supplier_request": None,
        "supplier_profiles_search_query": "",
        "supplier_profiles_delete_confirm": False,
        "supplier_transform_attention_required": False,
        "supplier_compare_info_message": None,
    }
    for key, value in defaults.items():
        if key not in session_state:
            session_state[key] = value
