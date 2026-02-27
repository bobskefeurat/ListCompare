from __future__ import annotations

import csv
import io
import json
from datetime import date
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from ..core.comparison_use_cases import (
    build_comparison_results,
    unique_sorted_skus_from_mismatch_side,
    unique_sorted_skus_from_product_map,
)
from ..core.product_diff import ProductMap, normalize_sku
from ..core.product_model import HICORE_COLUMNS, Product, build_product_map, prepare_data
from ..core.supplier_products import build_supplier_map, find_supplier_id_column

CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin1")
SUPPLIER_INDEX_PATH = (Path(__file__).resolve().parents[2] / "supplier_index.txt").resolve()
BRAND_INDEX_PATH = (Path(__file__).resolve().parents[2] / "brand_index.txt").resolve()
UI_SETTINGS_PATH = (Path(__file__).resolve().parents[2] / "ui_settings.json").resolve()
SUPPLIER_TRANSFORM_PROFILES_PATH = (
    Path(__file__).resolve().parents[2] / "supplier_transform_profiles.json"
).resolve()


MENU_COMPARE = "J\u00e4mf\u00f6r Hicore/Magento"
MENU_SUPPLIER = "Hantera leverant\u00f6r"
MENU_SETTINGS = "Inst\u00e4llningar"
SUPPLIER_PAGE_VIEW_COMPARE = "J\u00e4mf\u00f6relse"
SUPPLIER_PAGE_VIEW_TRANSFORM = "Leverant\u00f6rsprofiler"
SUPPLIER_PROFILE_MODE_OVERVIEW = "overview"
SUPPLIER_PROFILE_MODE_EDITOR = "editor"

SUPPLIER_HICORE_RENAME_COLUMNS = (
    "Art.m\u00e4rkning",
    "Artikelnamn",
    "Varum\u00e4rke",
    "Ink\u00f6pspris",
    "UtprisInklMoms",
    "Lev.artnr",
)
SUPPLIER_HICORE_SUPPLIER_COLUMN = "Leverant\u00f6r"
SUPPLIER_HICORE_SKU_COLUMN = "Art.m\u00e4rkning"

SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS = "strip_leading_zeros_from_sku"
SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU = "ignore_rows_missing_sku"
SUPPLIER_TRANSFORM_DEFAULT_OPTIONS: dict[str, bool] = {
    SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS: False,
    SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU: False,
}

FILE_STATE_KEYS = {
    "hicore": "stored_hicore_file",
    "magento": "stored_magento_file",
    "supplier": "stored_supplier_file",
}

UPLOADER_KEYS_BY_KIND = {
    "hicore": ("compare_hicore_uploader", "supplier_hicore_uploader"),
    "magento": ("compare_magento_uploader",),
    "supplier": ("supplier_file_uploader", "supplier_transform_uploader"),
}


@dataclass(frozen=True)
class CompareUiResult:
    only_in_magento_df: pd.DataFrame
    stock_mismatch_df: pd.DataFrame
    only_in_magento_csv_bytes: bytes
    stock_mismatch_csv_bytes: bytes
    only_in_magento_count: int
    stock_mismatch_count: int
    warning_message: Optional[str]


@dataclass(frozen=True)
class SupplierUiResult:
    internal_only_df: pd.DataFrame
    internal_only_csv_bytes: bytes
    internal_only_count: int
    warning_message: Optional[str]


def _normalize_supplier_transform_profile_mapping(
    raw_mapping: dict[object, object],
) -> dict[str, str]:
    normalized_mapping: dict[str, str] = {}
    for target_column in SUPPLIER_HICORE_RENAME_COLUMNS:
        if target_column not in raw_mapping:
            continue
        source_column = str(raw_mapping[target_column]).strip()
        if source_column == "":
            continue
        normalized_mapping[target_column] = source_column
    return normalized_mapping


def _normalize_supplier_transform_profile_options(
    raw_options: dict[object, object],
) -> dict[str, bool]:
    normalized_options = dict(SUPPLIER_TRANSFORM_DEFAULT_OPTIONS)
    for option_name, default_value in SUPPLIER_TRANSFORM_DEFAULT_OPTIONS.items():
        raw_value = raw_options.get(option_name, default_value)
        if isinstance(raw_value, bool):
            normalized_options[option_name] = raw_value
            continue
        if isinstance(raw_value, (int, float)):
            normalized_options[option_name] = bool(raw_value)
            continue
        if isinstance(raw_value, str):
            folded = raw_value.strip().casefold()
            if folded in ("1", "true", "yes", "ja", "on"):
                normalized_options[option_name] = True
            elif folded in ("0", "false", "no", "nej", "off", ""):
                normalized_options[option_name] = False
    return normalized_options


def _normalize_supplier_transform_profile(
    raw_profile: dict[object, object],
) -> tuple[dict[str, str], dict[str, bool]]:
    profile_mapping_raw = raw_profile.get("target_to_source", raw_profile)
    mapping = (
        _normalize_supplier_transform_profile_mapping(profile_mapping_raw)
        if isinstance(profile_mapping_raw, dict)
        else {}
    )
    raw_options = raw_profile.get("options", {})
    options = (
        _normalize_supplier_transform_profile_options(raw_options)
        if isinstance(raw_options, dict)
        else dict(SUPPLIER_TRANSFORM_DEFAULT_OPTIONS)
    )
    return mapping, options


def _ordered_supplier_transform_profile_mapping(mapping: dict[str, str]) -> dict[str, str]:
    return {
        target: mapping[target]
        for target in SUPPLIER_HICORE_RENAME_COLUMNS
        if target in mapping
    }


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


def _profile_has_required_sku_mapping(mapping: dict[str, str]) -> bool:
    return str(mapping.get(SUPPLIER_HICORE_SKU_COLUMN, "")).strip() != ""


def _missing_profile_source_columns(
    mapping: dict[str, str],
    source_columns: list[str],
) -> list[str]:
    available_columns = {str(column).strip() for column in source_columns}
    missing = {
        str(source).strip()
        for source in mapping.values()
        if str(source).strip() not in available_columns
    }
    return sorted(missing, key=lambda item: item.casefold())


def _matches_profile_output_format(
    mapping: dict[str, str],
    source_columns: list[str],
) -> bool:
    available_columns = {str(column).strip() for column in source_columns}
    required_targets = [
        target for target in SUPPLIER_HICORE_RENAME_COLUMNS if str(mapping.get(target, "")).strip() != ""
    ]
    if not required_targets:
        return False
    has_all_targets = all(target in available_columns for target in required_targets)
    has_supplier_column = SUPPLIER_HICORE_SUPPLIER_COLUMN in available_columns
    return has_all_targets and has_supplier_column


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


def _filter_supplier_names(names: list[str], query: str) -> list[str]:
    normalized_query = str(query).strip().casefold()
    if normalized_query == "":
        return list(names)
    return [name for name in names if normalized_query in str(name).casefold()]


def _selected_dataframe_row_index(selection_event: object) -> Optional[int]:
    selection = getattr(selection_event, "selection", None)
    if selection is None:
        return None

    selected_rows = getattr(selection, "rows", None)
    if isinstance(selected_rows, (list, tuple)) and selected_rows:
        try:
            return int(selected_rows[0])
        except Exception:
            pass

    selected_cells = getattr(selection, "cells", None)
    if isinstance(selected_cells, (list, tuple)) and selected_cells:
        first_cell = selected_cells[0]
        if isinstance(first_cell, dict):
            row_value = first_cell.get("row")
            try:
                return int(row_value)
            except Exception:
                return None
        if isinstance(first_cell, (list, tuple)) and first_cell:
            try:
                return int(first_cell[0])
            except Exception:
                return None
    return None


def _safe_filename_part(value: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    cleaned = "".join("_" if ch in invalid_chars else ch for ch in str(value).strip())
    cleaned = "_".join(part for part in cleaned.split())
    return cleaned if cleaned != "" else "leverantor"


def _rebuilt_supplier_file_name(supplier_name: str, *, extension: str = ".xlsx") -> str:
    safe_supplier = _safe_filename_part(supplier_name)
    normalized_extension = str(extension).strip()
    if normalized_extension == "":
        normalized_extension = ".xlsx"
    if not normalized_extension.startswith("."):
        normalized_extension = f".{normalized_extension}"
    return f"{safe_supplier}_prislista_{date.today().isoformat()}{normalized_extension}"


def _load_supplier_transform_profiles(
    path: Path,
) -> tuple[dict[str, dict[str, object]], Optional[str]]:
    if not path.exists():
        return {}, None

    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, dict):
            raise ValueError("supplier_transform_profiles.json måste innehålla ett JSON-objekt.")

        raw_profiles = raw.get("profiles", raw)
        if not isinstance(raw_profiles, dict):
            raise ValueError('Fältet "profiles" måste vara ett JSON-objekt.')

        profiles: dict[str, dict[str, object]] = {}
        for raw_supplier_name, raw_profile in raw_profiles.items():
            supplier_name = str(raw_supplier_name).strip()
            if supplier_name == "":
                continue
            if not isinstance(raw_profile, dict):
                continue

            mapping, options = _normalize_supplier_transform_profile(raw_profile)
            if mapping:
                profiles[supplier_name] = {
                    "target_to_source": _ordered_supplier_transform_profile_mapping(mapping),
                    "options": options,
                }

        return profiles, None
    except Exception as exc:
        return {}, str(exc)


def _save_supplier_transform_profiles(
    path: Path,
    *,
    profiles: dict[str, dict[str, object]],
) -> Optional[str]:
    payload_profiles: dict[str, dict[str, object]] = {}
    for raw_supplier_name, raw_profile in profiles.items():
        supplier_name = str(raw_supplier_name).strip()
        if supplier_name == "":
            continue
        if not isinstance(raw_profile, dict):
            continue
        mapping, options = _normalize_supplier_transform_profile(raw_profile)
        if not mapping:
            continue
        payload_profiles[supplier_name] = {
            "target_to_source": _ordered_supplier_transform_profile_mapping(mapping),
            "options": options,
        }

    payload = {"profiles": payload_profiles}
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return None
    except Exception as exc:
        return str(exc)


def _load_ui_settings(path: Path) -> tuple[dict[str, list[str]], Optional[str]]:
    default_settings: dict[str, list[str]] = {"excluded_brands": []}
    if not path.exists():
        return default_settings, None

    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, dict):
            raise ValueError("ui_settings.json måste innehålla ett JSON-objekt.")

        raw_excluded = raw.get("excluded_brands", [])
        if not isinstance(raw_excluded, list):
            raise ValueError('Fältet "excluded_brands" måste vara en lista.')

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
        return "Kan inte spara profil utan leverantörsnamn."

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
        return "Kan inte ta bort profil utan leverantörsnamn."

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


def _uploaded_csv_to_df(
    data: bytes,
    *,
    sep: str | None,
    engine: Optional[str] = None,
    extra_read_csv_kwargs: Optional[dict[str, object]] = None,
) -> pd.DataFrame:
    last_err: Optional[Exception] = None
    for enc in CSV_ENCODINGS:
        try:
            text = data.decode(enc)
            kwargs: dict[str, object] = {
                "sep": sep,
                "dtype": str,
                "index_col": False,
            }
            if engine is not None:
                kwargs["engine"] = engine
            if extra_read_csv_kwargs:
                kwargs.update(extra_read_csv_kwargs)
            return pd.read_csv(io.StringIO(text), **kwargs)
        except UnicodeDecodeError as err:
            last_err = err
        except Exception as err:
            last_err = err
    if last_err is not None:
        raise last_err
    raise UnicodeDecodeError("utf-8", b"", 0, 1, "Unable to decode uploaded CSV")


def _read_supplier_csv_upload(data: bytes) -> pd.DataFrame:
    try:
        return _uploaded_csv_to_df(data, sep=None, engine="python")
    except Exception as first_error:
        fallback_error: Exception = first_error

        for sep in (";", ",", "\t", "|"):
            try:
                return _uploaded_csv_to_df(data, sep=sep, engine="python")
            except Exception as err:
                fallback_error = err

        for sep in (";", ",", "\t", "|"):
            try:
                return _uploaded_csv_to_df(
                    data,
                    sep=sep,
                    engine="python",
                    extra_read_csv_kwargs={
                        # Fallback for malformed CSV quotes in some supplier exports.
                        "quoting": csv.QUOTE_NONE,
                    },
                )
            except Exception as err:
                fallback_error = err

        raise ValueError(
            "Kunde inte l\u00e4sa CSV-filen. Filen verkar inneh\u00e5lla trasig CSV-formatering "
            f"(t.ex. citattecken). Originalfel: {first_error}. Senaste fallback-fel: {fallback_error}"
        ) from first_error


def _normalize_supplier_names(raw_names: list[str]) -> list[str]:
    unique_by_folded: dict[str, str] = {}
    for raw_name in raw_names:
        supplier_name = str(raw_name).strip()
        if supplier_name == "" or supplier_name.casefold() == "nan":
            continue
        folded = supplier_name.casefold()
        if folded not in unique_by_folded:
            unique_by_folded[folded] = supplier_name

    return sorted(unique_by_folded.values(), key=lambda name: name.casefold())


def _supplier_names_from_hicore_df(df_hicore: pd.DataFrame) -> list[str]:
    supplier_col = HICORE_COLUMNS["supplier"]
    if supplier_col not in df_hicore.columns:
        return []
    raw_names: list[str] = [
        str(value)
        for value in df_hicore[supplier_col].tolist()
        if not pd.isna(value)
    ]
    return _normalize_supplier_names(raw_names)


def _brand_names_from_hicore_df(df_hicore: pd.DataFrame) -> list[str]:
    brand_col = HICORE_COLUMNS.get("brand")
    if brand_col is None or brand_col not in df_hicore.columns:
        return []
    raw_names: list[str] = [
        str(value)
        for value in df_hicore[brand_col].tolist()
        if not pd.isna(value)
    ]
    return _normalize_supplier_names(raw_names)


def _load_suppliers_from_index(path: Path) -> tuple[list[str], Optional[str]]:
    if not path.exists():
        return [], f"Saknar leverant\u00f6rsindex: {path.name}"

    try:
        content = path.read_text(encoding="utf-8-sig")
        suppliers = _normalize_supplier_names(content.splitlines())
        return suppliers, None
    except Exception as exc:
        return [], str(exc)


def _save_suppliers_to_index(path: Path, suppliers: list[str]) -> None:
    normalized = _normalize_supplier_names(suppliers)
    body = "\n".join(normalized)
    if body != "":
        body += "\n"
    path.write_text(body, encoding="utf-8-sig")


def _load_brands_from_index(path: Path) -> tuple[list[str], Optional[str]]:
    if not path.exists():
        return [], f"Saknar varum\u00e4rkesindex: {path.name}"

    try:
        content = path.read_text(encoding="utf-8-sig")
        brands = _normalize_supplier_names(content.splitlines())
        return brands, None
    except Exception as exc:
        return [], str(exc)


def _save_brands_to_index(path: Path, brands: list[str]) -> None:
    normalized = _normalize_supplier_names(brands)
    body = "\n".join(normalized)
    if body != "":
        body += "\n"
    path.write_text(body, encoding="utf-8-sig")


def _merge_supplier_lists(existing: list[str], discovered: list[str]) -> tuple[list[str], list[str]]:
    by_folded: dict[str, str] = {}
    for name in _normalize_supplier_names(existing):
        by_folded[name.casefold()] = name

    new_names: list[str] = []
    for name in _normalize_supplier_names(discovered):
        folded = name.casefold()
        if folded not in by_folded:
            by_folded[folded] = name
            new_names.append(name)

    merged = sorted(by_folded.values(), key=lambda value: value.casefold())
    return merged, new_names


def _merge_brand_lists(existing: list[str], discovered: list[str]) -> tuple[list[str], list[str]]:
    return _merge_supplier_lists(existing, discovered)


@st.cache_data(show_spinner=False)
def _load_names_from_uploaded_hicore(
    uploaded_name: str,
    uploaded_bytes: bytes,
) -> tuple[list[str], list[str], bool, bool]:
    del uploaded_name
    df_hicore = _uploaded_csv_to_df(uploaded_bytes, sep=";")
    supplier_col = HICORE_COLUMNS["supplier"]
    brand_col = HICORE_COLUMNS.get("brand")
    return (
        _supplier_names_from_hicore_df(df_hicore),
        _brand_names_from_hicore_df(df_hicore),
        supplier_col in df_hicore.columns,
        bool(brand_col and brand_col in df_hicore.columns),
    )


def _normalized_skus_for_excluded_brands(
    df_hicore: pd.DataFrame,
    excluded_brands: list[str],
) -> tuple[set[str], Optional[str]]:
    selected_brands = _normalize_supplier_names(excluded_brands)
    if not selected_brands:
        return set(), None

    brand_col = HICORE_COLUMNS.get("brand")
    if brand_col is None or brand_col not in df_hicore.columns:
        return set(), 'HiCore-filen saknar kolumnen "Varum\u00e4rke". Varum\u00e4rkesexkludering ignorerades.'

    sku_col = HICORE_COLUMNS["sku"]
    if sku_col not in df_hicore.columns:
        return set(), None

    selected_folded = {name.casefold() for name in selected_brands}
    excluded_normalized_skus: set[str] = set()
    for _, row in df_hicore.iterrows():
        raw_brand = row.get(brand_col, "")
        if pd.isna(raw_brand):
            continue

        brand_name = str(raw_brand).strip()
        if brand_name == "" or brand_name.casefold() == "nan":
            continue
        if brand_name.casefold() not in selected_folded:
            continue

        raw_sku = row.get(sku_col, "")
        if pd.isna(raw_sku):
            continue

        normalized = normalize_sku(str(raw_sku))
        if normalized != "":
            excluded_normalized_skus.add(normalized)

    return excluded_normalized_skus, None


def _read_supplier_upload(file_name: str, data: bytes) -> pd.DataFrame:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".csv":
        return _read_supplier_csv_upload(data)
    if suffix in (".xlsx", ".xls", ".xlsm"):
        return pd.read_excel(io.BytesIO(data), dtype=str)
    raise ValueError(f"Unsupported supplier file type: {file_name}")


def _product_map_to_df(product_map: ProductMap) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for key, products in product_map.items():
        for product in products:
            rows.append(
                {
                    "map_key": key,
                    "sku": product.sku,
                    "name": product.name,
                    "stock": product.stock,
                    "supplier": product.supplier,
                    "source": product.source,
                }
            )

    if not rows:
        return pd.DataFrame(columns=["map_key", "sku", "name", "stock", "supplier", "source"])
    return pd.DataFrame(rows)


def _mismatch_map_to_df(mismatch_map: dict[str, dict[str, list[Product]]]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for normalized_sku, sides in mismatch_map.items():
        for side_name in ("hicore", "magento"):
            for product in sides.get(side_name, []):
                rows.append(
                    {
                        "normalized_sku": normalized_sku,
                        "side": side_name,
                        "sku": product.sku,
                        "name": product.name,
                        "stock": product.stock,
                        "supplier": product.supplier,
                        "source": product.source,
                    }
                )

    if not rows:
        return pd.DataFrame(
            columns=["normalized_sku", "side", "sku", "name", "stock", "supplier", "source"]
        )
    return pd.DataFrame(rows)


def _style_stock_mismatch_df(df: pd.DataFrame):
    if df.empty:
        return df.style

    colors = ("#f3f3f3", "#ffffff")
    row_colors: list[str] = []
    if "normalized_sku" in df.columns:
        previous_key: Optional[str] = None
        group_index = -1
        for value in df["normalized_sku"].tolist():
            current_key = "" if pd.isna(value) else str(value)
            if previous_key is None or current_key != previous_key:
                group_index += 1
                previous_key = current_key
            row_colors.append(colors[group_index % 2])
    else:
        row_colors = [colors[(idx // 2) % 2] for idx in range(len(df))]

    index_to_color = dict(zip(df.index.tolist(), row_colors))
    return df.style.apply(
        lambda row: [f"background-color: {index_to_color.get(row.name, colors[1])}"] * len(row),
        axis=1,
    )


def _sku_csv_bytes(skus: list[str]) -> bytes:
    df = pd.DataFrame({"Art.m\u00e4rkning": skus})
    return df.to_csv(sep=";", index=False).encode("utf-8-sig")


def _df_csv_bytes(df: pd.DataFrame, *, sep: str = ";") -> bytes:
    return df.to_csv(sep=sep, index=False).encode("utf-8-sig")


def _df_excel_bytes(df: pd.DataFrame, *, sheet_name: str = "Sheet1") -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()


def _find_duplicate_names(values: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    duplicates: list[str] = []
    for value in values:
        counts[value] = counts.get(value, 0) + 1
        if counts[value] == 2:
            duplicates.append(value)
    return sorted(duplicates, key=lambda item: item.casefold())


def _normalize_supplier_transform_sku_value(
    raw_value: object,
    *,
    strip_leading_zeros: bool,
) -> str:
    if pd.isna(raw_value):
        return ""
    value = str(raw_value).strip()
    if value == "" or value.casefold() == "nan":
        return ""
    if strip_leading_zeros:
        value = value.lstrip("0")
        if value == "":
            return "0"
    return value


def _build_supplier_hicore_renamed_copy(
    df_supplier: pd.DataFrame,
    *,
    target_to_source: dict[str, str],
    supplier_name: str,
    strip_leading_zeros_from_sku: bool = False,
    ignore_rows_missing_sku: bool = False,
) -> pd.DataFrame:
    normalized_target_to_source = {
        str(target).strip(): str(source).strip()
        for target, source in target_to_source.items()
        if str(target).strip() in SUPPLIER_HICORE_RENAME_COLUMNS and str(source).strip() != ""
    }
    if not normalized_target_to_source:
        raise ValueError("Matcha minst en HiCore-kolumn innan export.")
    normalized_supplier_name = str(supplier_name).strip()
    if normalized_supplier_name == "":
        raise ValueError("V\u00e4lj leverant\u00f6r fr\u00e5n leverant\u00f6rslistan innan export.")

    prepared_df = df_supplier.copy()
    prepared_df.columns = [str(col).strip() for col in prepared_df.columns]

    selected_sources = [str(source).strip() for source in normalized_target_to_source.values()]
    duplicate_sources = _find_duplicate_names(selected_sources)
    if duplicate_sources:
        raise ValueError(
            "Samma leverant\u00f6rskolumn kan inte mappas till flera HiCore-kolumner: "
            + ", ".join(duplicate_sources)
        )

    available_columns = {str(col).strip() for col in prepared_df.columns}
    missing_sources = sorted(
        [source for source in selected_sources if source not in available_columns],
        key=lambda item: item.casefold(),
    )
    if missing_sources:
        raise ValueError(
            "Vald(e) kolumn(er) finns inte i leverant\u00f6rsfilen: " + ", ".join(missing_sources)
        )

    sku_source_column = normalized_target_to_source.get(SUPPLIER_HICORE_SKU_COLUMN)
    if sku_source_column is not None:
        normalized_sku_values = prepared_df[sku_source_column].map(
            lambda raw_value: _normalize_supplier_transform_sku_value(
                raw_value,
                strip_leading_zeros=strip_leading_zeros_from_sku,
            )
        )
        prepared_df.loc[:, sku_source_column] = normalized_sku_values
        if ignore_rows_missing_sku:
            prepared_df = prepared_df.loc[normalized_sku_values != ""].copy()

    rename_map = {
        str(source).strip(): str(target).strip()
        for target, source in normalized_target_to_source.items()
    }
    ordered_targets = [target for target in SUPPLIER_HICORE_RENAME_COLUMNS if target in normalized_target_to_source]
    ordered_sources = [str(normalized_target_to_source[target]).strip() for target in ordered_targets]
    renamed_df = prepared_df.loc[:, ordered_sources].copy().rename(columns=rename_map)
    renamed_df[SUPPLIER_HICORE_SUPPLIER_COLUMN] = normalized_supplier_name
    renamed_df = renamed_df.loc[
        :,
        [*ordered_targets, SUPPLIER_HICORE_SUPPLIER_COLUMN],
    ]

    output_columns = [str(col).strip() for col in renamed_df.columns]
    duplicate_output_columns = _find_duplicate_names(output_columns)
    if duplicate_output_columns:
        raise ValueError(
            "Resultatfilen skulle f\u00e5 dubblettkolumner efter namnbyte: "
            + ", ".join(duplicate_output_columns)
        )

    return renamed_df


def _compute_compare_result(
    hicore_bytes: bytes,
    magento_bytes: bytes,
    *,
    excluded_brands: Optional[list[str]] = None,
) -> CompareUiResult:
    df_hicore = _uploaded_csv_to_df(hicore_bytes, sep=";")
    df_magento = _uploaded_csv_to_df(magento_bytes, sep=";")
    hicore_map, magento_map = prepare_data(df_hicore, df_magento)
    excluded_normalized_skus, warning_message = _normalized_skus_for_excluded_brands(
        df_hicore,
        excluded_brands or [],
    )

    results = build_comparison_results(
        hicore_map,
        magento_map,
        excluded_normalized_skus=excluded_normalized_skus,
    )

    only_in_magento_skus = unique_sorted_skus_from_product_map(results.only_in_magento)
    stock_skus = unique_sorted_skus_from_mismatch_side(results.stock_mismatches, "magento")
    return CompareUiResult(
        only_in_magento_df=_product_map_to_df(results.only_in_magento),
        stock_mismatch_df=_mismatch_map_to_df(results.stock_mismatches),
        only_in_magento_csv_bytes=_sku_csv_bytes(only_in_magento_skus),
        stock_mismatch_csv_bytes=_sku_csv_bytes(stock_skus),
        only_in_magento_count=len(results.only_in_magento),
        stock_mismatch_count=len(results.stock_mismatches),
        warning_message=warning_message,
    )


def _compute_supplier_result(
    hicore_bytes: bytes,
    *,
    supplier_name: str,
    supplier_file_name: str,
    supplier_bytes: bytes,
    excluded_brands: Optional[list[str]] = None,
) -> SupplierUiResult:
    df_hicore = _uploaded_csv_to_df(hicore_bytes, sep=";")
    hicore_map = build_product_map(
        df_hicore,
        source="hicore",
        columns=HICORE_COLUMNS,
    )
    excluded_normalized_skus, warning_message = _normalized_skus_for_excluded_brands(
        df_hicore,
        excluded_brands or [],
    )
    df_supplier = _read_supplier_upload(supplier_file_name, supplier_bytes)
    supplier_map = build_supplier_map(df_supplier)
    results = build_comparison_results(
        hicore_map,
        {},
        supplier_map=supplier_map,
        supplier_internal_name=supplier_name,
        excluded_normalized_skus=excluded_normalized_skus,
    )

    internal_only_map = results.internal_only_candidates or {}
    internal_only_skus = unique_sorted_skus_from_product_map(internal_only_map)
    return SupplierUiResult(
        internal_only_df=_product_map_to_df(internal_only_map),
        internal_only_csv_bytes=_sku_csv_bytes(internal_only_skus),
        internal_only_count=len(internal_only_map),
        warning_message=warning_message,
    )


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


def _render_supplier_results(result: SupplierUiResult) -> None:
    if result.warning_message:
        st.warning(result.warning_message)

    st.metric("Internal only (supplier)", result.internal_only_count)
    st.download_button(
        label="Ladda ner internal_only_skus.csv",
        data=result.internal_only_csv_bytes,
        file_name="internal_only_skus.csv",
        mime="text/csv",
        key="download_internal_only_csv",
    )
    st.dataframe(result.internal_only_df, use_container_width=True)


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


def _render_supplier_compare_tab(
    *,
    supplier_options: list[str],
    supplier_index_error: Optional[str],
    new_supplier_names: list[str],
    excluded_brands: list[str],
) -> None:
    normalized_compare_supplier = _normalize_selected_supplier_for_options(
        st.session_state.get("supplier_internal_name"),
        supplier_options,
    )
    if st.session_state.get("supplier_internal_name") != normalized_compare_supplier:
        st.session_state["supplier_internal_name"] = normalized_compare_supplier

    hicore_file = _render_file_input(
        kind="hicore",
        label="HiCore-export (.csv)",
        file_types=["csv"],
        uploader_key="supplier_hicore_uploader",
    )
    supplier_file = _render_file_input(
        kind="supplier",
        label="Leverant\u00f6rsfil (.csv/.xlsx/.xls/.xlsm)",
        file_types=["csv", "xlsx", "xls", "xlsm"],
        uploader_key="supplier_file_uploader",
    )
    info_message = st.session_state.get("supplier_compare_info_message")
    if info_message:
        st.success(str(info_message))
        st.session_state["supplier_compare_info_message"] = None

    previous_supplier_name = st.session_state.get("_last_supplier_internal_name")
    supplier_internal_name = st.selectbox(
        "V\u00e4lj leverant\u00f6r",
        options=supplier_options,
        index=None,
        placeholder="V\u00e4lj leverant\u00f6r...",
        key="supplier_internal_name",
    )
    if previous_supplier_name != supplier_internal_name:
        st.session_state["_last_supplier_internal_name"] = supplier_internal_name
        _clear_supplier_state()
    selected_supplier_name = (
        str(supplier_internal_name).strip() if supplier_internal_name is not None else ""
    )
    if st.session_state.get("supplier_profiles_active_supplier") != (
        selected_supplier_name if selected_supplier_name != "" else None
    ):
        st.session_state["supplier_profiles_active_supplier"] = (
            selected_supplier_name if selected_supplier_name != "" else None
        )
    _sync_selected_supplier_between_views(
        selected_supplier_name if selected_supplier_name != "" else None,
        supplier_options,
        target_key="supplier_transform_internal_name",
    )

    profile_mapping, profile_options = _get_supplier_transform_profile(selected_supplier_name)
    profile_exists = bool(profile_mapping)
    profile_has_required_sku = _profile_has_required_sku_mapping(profile_mapping)
    profile_ready = profile_exists and profile_has_required_sku
    st.session_state["supplier_transform_attention_required"] = (
        selected_supplier_name != "" and not profile_ready
    )

    supplier_file_read_error: Optional[str] = None
    supplier_file_direct_compare_format = False
    profile_matches_uploaded_file = False
    file_matches_profile_output_format = False
    missing_profile_columns_for_file: list[str] = []
    df_supplier_uploaded: Optional[pd.DataFrame] = None
    if supplier_file is not None:
        supplier_file_name = str(supplier_file["name"])  # type: ignore[index]
        supplier_bytes = supplier_file["bytes"]  # type: ignore[index]
        try:
            df_supplier_uploaded = _read_supplier_upload(supplier_file_name, supplier_bytes)
            source_columns = [str(column).strip() for column in df_supplier_uploaded.columns]
            try:
                find_supplier_id_column(df_supplier_uploaded)
                supplier_file_direct_compare_format = True
            except Exception:
                supplier_file_direct_compare_format = False

            if profile_ready:
                missing_profile_columns_for_file = _missing_profile_source_columns(
                    profile_mapping,
                    source_columns,
                )
                profile_matches_uploaded_file = len(missing_profile_columns_for_file) == 0
                file_matches_profile_output_format = _matches_profile_output_format(
                    profile_mapping,
                    source_columns,
                )
        except Exception as exc:
            supplier_file_read_error = str(exc)

    if selected_supplier_name == "":
        st.info("V\u00e4lj leverant\u00f6r f\u00f6r att kontrollera profilstatus.")
    elif not profile_exists:
        st.error(
            f'Saknar sparad leverant\u00f6rsprofil f\u00f6r "{selected_supplier_name}". '
            "Skapa en profil i fliken Leverantörsprofiler."
        )
    elif not profile_has_required_sku:
        st.error(
            f'Profilen f\u00f6r "{selected_supplier_name}" saknar mappning av "{SUPPLIER_HICORE_SKU_COLUMN}". '
            "SKU m\u00e5ste alltid vara matchad."
        )
    else:
        st.success(f'F\u00e4rdig leverant\u00f6rsprofil hittad f\u00f6r "{selected_supplier_name}".')

    if supplier_file is not None:
        if supplier_file_read_error is not None:
            st.error(f"Kunde inte l\u00e4sa leverant\u00f6rsfilen: {supplier_file_read_error}")
        elif profile_ready and file_matches_profile_output_format:
            st.success("Uppladdad leverant\u00f6rsfil matchar redan sparad profil i HiCore-format.")
        elif profile_ready and profile_matches_uploaded_file:
            st.info(
                "Leverant\u00f6rsfilen kan byggas om via profil. Tryck p\u00e5 \"Bygg om till Hicore-format\"."
            )
        elif profile_ready:
            st.warning(
                "Uppladdad leverant\u00f6rsfil matchar inte den sparade profilen. Saknade kolumner: "
                + ", ".join(missing_profile_columns_for_file)
            )

    can_run = (
        hicore_file is not None
        and supplier_file is not None
        and selected_supplier_name != ""
        and profile_ready
        and supplier_file_read_error is None
        and supplier_file_direct_compare_format
    )
    run_clicked = st.button(
        "K\u00f6r J\u00e4mf\u00f6relse",
        type="primary",
        disabled=not can_run,
        key="run_supplier_button",
    )

    can_rebuild_uploaded_file = (
        supplier_file is not None
        and selected_supplier_name != ""
        and profile_ready
        and supplier_file_read_error is None
        and profile_matches_uploaded_file
        and not file_matches_profile_output_format
        and df_supplier_uploaded is not None
    )
    can_manage_profile = selected_supplier_name != ""
    profile_action_label = (
        "Uppdatera leverant\u00f6rsprofil" if profile_exists else "Skapa leverant\u00f6rsprofil"
    )
    rebuild_col, profile_col = st.columns(2)
    if rebuild_col.button(
        "Bygg om till Hicore-format",
        type="secondary",
        disabled=not can_rebuild_uploaded_file,
        key="rebuild_supplier_file_with_profile_button",
    ):
        try:
            normalized_profile_options = _normalize_supplier_transform_profile_options(profile_options)
            rebuilt_df = _build_supplier_hicore_renamed_copy(
                df_supplier_uploaded,  # type: ignore[arg-type]
                target_to_source=profile_mapping,
                supplier_name=selected_supplier_name,
                strip_leading_zeros_from_sku=normalized_profile_options[
                    SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS
                ],
                ignore_rows_missing_sku=normalized_profile_options[
                    SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU
                ],
            )
            rebuilt_name = _rebuilt_supplier_file_name(selected_supplier_name)
            st.session_state[FILE_STATE_KEYS["supplier"]] = {
                "name": rebuilt_name,
                "bytes": _df_excel_bytes(rebuilt_df, sheet_name="HiCore-format"),
            }
            st.session_state["supplier_compare_info_message"] = (
                f'Leverant\u00f6rsfilen byggdes om med profilen f\u00f6r "{selected_supplier_name}" '
                "och ersatte tidigare uppladdad fil."
            )
            _clear_all_run_state()
            _rerun()
        except Exception as exc:
            st.session_state["supplier_ui_result"] = None
            st.session_state["supplier_ui_error"] = f"Kunde inte bygga om leverant\u00f6rsfilen: {exc}"
    if profile_col.button(
        profile_action_label,
        type="secondary",
        disabled=not can_manage_profile,
        key="update_supplier_profile_button",
    ):
        _request_supplier_profile_editor(selected_supplier_name)

    if run_clicked:
        try:
            result = _compute_supplier_result(
                hicore_bytes=hicore_file["bytes"],  # type: ignore[index]
                supplier_name=selected_supplier_name,
                supplier_file_name=str(supplier_file["name"]),  # type: ignore[index]
                supplier_bytes=supplier_file["bytes"],  # type: ignore[index]
                excluded_brands=[str(name) for name in excluded_brands],
            )
            st.session_state["supplier_ui_result"] = result
            st.session_state["supplier_ui_error"] = None
        except Exception as exc:
            st.session_state["supplier_ui_result"] = None
            st.session_state["supplier_ui_error"] = str(exc)

    st.caption(f"Antal leverant\u00f6rer: {len(supplier_options)}")
    if new_supplier_names:
        st.success(
            f"Uppdaterade {SUPPLIER_INDEX_PATH.name} med {len(new_supplier_names)} ny(a) leverant\u00f6r(er) fr\u00e5n HiCore."
        )
    if supplier_index_error:
        st.warning(
            f"Kunde inte l\u00e4sa {SUPPLIER_INDEX_PATH.name} vid uppstart: {supplier_index_error}"
        )

    if st.session_state["supplier_ui_error"]:
        st.error(st.session_state["supplier_ui_error"])
    if st.session_state["supplier_ui_result"] is not None:
        _render_supplier_results(st.session_state["supplier_ui_result"])


def _render_supplier_profile_editor(
    *,
    supplier_options: list[str],
    supplier_index_error: Optional[str],
) -> None:
    normalized_transform_supplier = _normalize_selected_supplier_for_options(
        st.session_state.get("supplier_internal_name"),
        supplier_options,
    )
    if st.session_state.get("supplier_internal_name") != normalized_transform_supplier:
        st.session_state["supplier_internal_name"] = normalized_transform_supplier
    if st.session_state.get("supplier_transform_internal_name") != normalized_transform_supplier:
        st.session_state["supplier_transform_internal_name"] = normalized_transform_supplier

    st.subheader("Profilredigering")
    st.caption(
        "Matcha leverant\u00f6rens kolumner mot HiCore-kolumner och exportera en kopia med omd\u00f6pta kolumnnamn."
    )
    st.caption(
        f'Kolumnen "{SUPPLIER_HICORE_SUPPLIER_COLUMN}" s\u00e4tts fr\u00e5n vald leverant\u00f6r i leverant\u00f6rslistan.'
    )
    st.caption("Endast matchade kolumner exporteras. Resultatet exporteras som Excel (.xlsx).")

    supplier_file = _render_file_input(
        kind="supplier",
        label="Leverant\u00f6rsfil (.csv/.xlsx/.xls/.xlsm)",
        file_types=["csv", "xlsx", "xls", "xlsm"],
        uploader_key="supplier_transform_uploader",
    )

    if supplier_index_error:
        st.warning(
            f"Kunde inte l\u00e4sa {SUPPLIER_INDEX_PATH.name} vid uppstart: {supplier_index_error}"
        )
    if st.session_state.get("supplier_transform_profiles_load_error"):
        st.warning(
            "Kunde inte l\u00e4sa "
            f"{SUPPLIER_TRANSFORM_PROFILES_PATH.name} vid uppstart: "
            f"{st.session_state['supplier_transform_profiles_load_error']}"
        )
    if st.session_state.get("supplier_transform_profiles_save_error"):
        st.warning(
            f"Kunde inte spara {SUPPLIER_TRANSFORM_PROFILES_PATH.name}: "
            f"{st.session_state['supplier_transform_profiles_save_error']}"
        )
    if not supplier_options:
        st.warning(
            f"Inga leverant\u00f6rer hittades i {SUPPLIER_INDEX_PATH.name}. L\u00e4gg till leverant\u00f6rer f\u00f6rst."
        )
        return
    supplier_internal_name = st.selectbox(
        "Leverant\u00f6r",
        options=supplier_options,
        index=None,
        placeholder="V\u00e4lj leverant\u00f6r fr\u00e5n supplier_index...",
        key="supplier_internal_name",
    )
    selected_supplier_name = (
        str(supplier_internal_name).strip() if supplier_internal_name is not None else ""
    )
    if st.session_state.get("supplier_profiles_active_supplier") != (
        selected_supplier_name if selected_supplier_name != "" else None
    ):
        st.session_state["supplier_profiles_active_supplier"] = (
            selected_supplier_name if selected_supplier_name != "" else None
        )
    _sync_selected_supplier_between_views(
        selected_supplier_name if selected_supplier_name != "" else None,
        supplier_options,
        target_key="supplier_transform_internal_name",
    )
    supplier_transform_profiles_raw = st.session_state.get("supplier_transform_profiles", {})
    supplier_transform_profiles = (
        supplier_transform_profiles_raw if isinstance(supplier_transform_profiles_raw, dict) else {}
    )
    saved_profile: dict[str, str] = {}
    saved_profile_options = dict(SUPPLIER_TRANSFORM_DEFAULT_OPTIONS)
    if selected_supplier_name:
        raw_profile = supplier_transform_profiles.get(selected_supplier_name, {})
        if isinstance(raw_profile, dict):
            saved_profile, saved_profile_options = _normalize_supplier_transform_profile(raw_profile)
    has_saved_profile = bool(saved_profile)

    action_col_back, action_col_delete, _ = st.columns([1, 1, 3])
    if action_col_back.button("Tillbaka", type="secondary", key="supplier_profile_back_button"):
        st.session_state["supplier_profiles_mode"] = SUPPLIER_PROFILE_MODE_OVERVIEW
        st.session_state["supplier_profiles_delete_confirm"] = False
        st.session_state["supplier_profiles_active_supplier"] = None
        _rerun()
    if action_col_delete.button(
        "Ta bort profil",
        type="secondary",
        disabled=not (selected_supplier_name != "" and has_saved_profile),
        key="supplier_profile_delete_button",
    ):
        st.session_state["supplier_profiles_delete_confirm"] = True
        _rerun()

    if st.session_state.get("supplier_profiles_delete_confirm", False):
        st.warning(f'Är du säker på att du vill ta bort profilen för "{selected_supplier_name}"?')
        confirm_col, cancel_col = st.columns(2)
        if confirm_col.button(
            "Bekräfta radering",
            type="primary",
            key="supplier_profile_delete_confirm_button",
        ):
            delete_error = _delete_supplier_transform_profile(supplier_name=selected_supplier_name)
            st.session_state["supplier_profiles_delete_confirm"] = False
            if delete_error is not None:
                st.error(delete_error)
            else:
                st.session_state["supplier_profiles_mode"] = SUPPLIER_PROFILE_MODE_OVERVIEW
                st.session_state["supplier_profiles_active_supplier"] = None
                _clear_supplier_state()
                _rerun()
        if cancel_col.button("Avbryt", key="supplier_profile_delete_cancel_button"):
            st.session_state["supplier_profiles_delete_confirm"] = False
            _rerun()

    if selected_supplier_name != "":
        st.markdown(f"**Profil: {selected_supplier_name}**")
        st.markdown("**Nuvarande inställningar**")
        if has_saved_profile:
            saved_rows = [
                {
                    "HiCore-kolumn": target_column,
                    "Leverantörskolumn": saved_profile.get(target_column, "(ej mappad)"),
                }
                for target_column in SUPPLIER_HICORE_RENAME_COLUMNS
            ]
            saved_rows.append(
                {
                    "HiCore-kolumn": SUPPLIER_HICORE_SUPPLIER_COLUMN,
                    "Leverantörskolumn": f"Värde från supplier_index: {selected_supplier_name}",
                }
            )
            st.dataframe(pd.DataFrame(saved_rows), use_container_width=True)
            st.caption(
                "SKU-regler: "
                f"ta bort inledande nollor = {'Ja' if saved_profile_options[SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS] else 'Nej'}, "
                f"ignorera rader utan SKU = {'Ja' if saved_profile_options[SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU] else 'Nej'}."
            )
        else:
            st.info("Ingen profil är sparad ännu för vald leverantör.")

    if supplier_file is None:
        if selected_supplier_name == "":
            st.info("V\u00e4lj leverant\u00f6r och ladda upp en leverant\u00f6rsfil f\u00f6r att mappa kolumner.")
        else:
            st.info(
                "Ladda upp en leverant\u00f6rsfil f\u00f6r att mappa kolumner f\u00f6r vald leverant\u00f6r. "
                "Uppladdning \u00e4r obligatorisk f\u00f6r att skapa eller uppdatera profil."
            )
        return

    supplier_file_name = str(supplier_file["name"])  # type: ignore[index]
    supplier_bytes = supplier_file["bytes"]  # type: ignore[index]
    try:
        df_supplier = _read_supplier_upload(supplier_file_name, supplier_bytes)
    except Exception as exc:
        st.error(f"Kunde inte l\u00e4sa leverant\u00f6rsfilen: {exc}")
        return

    source_columns = [str(col).strip() for col in df_supplier.columns]
    if not source_columns:
        st.warning("Leverant\u00f6rsfilen inneh\u00e5ller inga kolumnnamn.")
        return

    duplicate_source_columns = _find_duplicate_names(source_columns)
    if duplicate_source_columns:
        st.warning(
            "Filen inneh\u00e5ller dubblettkolumnnamn. Det kan g\u00f6ra mappningen tvetydig: "
            + ", ".join(duplicate_source_columns)
        )

    st.caption(f"Antal kolumner i leverant\u00f6rsfilen: {len(source_columns)}")
    st.dataframe(
        pd.DataFrame({"Leverant\u00f6rskolumner": source_columns}),
        use_container_width=True,
    )

    if selected_supplier_name == "":
        st.info("V\u00e4lj leverant\u00f6r f\u00f6r att kunna ladda eller spara en profil.")
    elif saved_profile:
        valid_saved_targets = [
            target
            for target, source in saved_profile.items()
            if target in SUPPLIER_HICORE_RENAME_COLUMNS and source in source_columns
        ]
        missing_saved_targets = [
            target
            for target, source in saved_profile.items()
            if target in SUPPLIER_HICORE_RENAME_COLUMNS and source not in source_columns
        ]
        if valid_saved_targets:
            st.success(
                f'Sparad profil hittad för "{selected_supplier_name}". '
                f"Förifyller {len(valid_saved_targets)} kolumnval."
            )
        if missing_saved_targets:
            st.warning(
                "Den sparade profilen matchar inte fullt ut mot aktuell fil. "
                "Välj om följande HiCore-kolumner: "
                + ", ".join(missing_saved_targets)
            )
    elif selected_supplier_name:
        st.info(
            f'Ingen sparad profil finns för "{selected_supplier_name}". '
            "Matcha kolumnerna och spara en profil."
        )

    st.subheader("Matcha mot HiCore-kolumner")
    supplier_key_token = selected_supplier_name if selected_supplier_name != "" else "no_supplier"
    file_token = f"{Path(supplier_file_name).name}_{len(supplier_bytes)}_{supplier_key_token}"
    target_to_source: dict[str, str] = {}

    for idx, target_column in enumerate(SUPPLIER_HICORE_RENAME_COLUMNS):
        widget_key = f"supplier_transform_map_{idx}_{file_token}"
        saved_source = saved_profile.get(target_column)
        if (
            widget_key not in st.session_state
            and saved_source is not None
            and str(saved_source).strip() in source_columns
        ):
            st.session_state[widget_key] = str(saved_source).strip()

        selected_source = st.selectbox(
            target_column,
            options=source_columns,
            index=None,
            placeholder="V\u00e4lj motsvarande kolumn i leverant\u00f6rsfilen...",
            key=widget_key,
        )
        if selected_source is not None and str(selected_source).strip() != "":
            target_to_source[target_column] = str(selected_source).strip()

    st.subheader("SKU-regler")
    st.caption(f'Gäller kolumnen "{SUPPLIER_HICORE_SKU_COLUMN}" när den är mappad.')
    strip_zeros_key = f"supplier_transform_option_strip_zeros_{file_token}"
    ignore_missing_sku_key = f"supplier_transform_option_ignore_missing_sku_{file_token}"
    if strip_zeros_key not in st.session_state:
        st.session_state[strip_zeros_key] = saved_profile_options[
            SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS
        ]
    if ignore_missing_sku_key not in st.session_state:
        st.session_state[ignore_missing_sku_key] = saved_profile_options[
            SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU
        ]
    strip_leading_zeros_from_sku = bool(
        st.checkbox("Ta bort inledande nollor i SKU", key=strip_zeros_key)
    )
    ignore_rows_missing_sku = bool(
        st.checkbox("Ignorera rader som saknar SKU", key=ignore_missing_sku_key)
    )

    selected_sources = [target_to_source[target] for target in target_to_source]
    duplicate_selected_sources = _find_duplicate_names(selected_sources)
    if duplicate_selected_sources:
        st.error(
            "Du har valt samma leverant\u00f6rskolumn flera g\u00e5nger: "
            + ", ".join(duplicate_selected_sources)
        )

    missing_target_columns = [
        column for column in SUPPLIER_HICORE_RENAME_COLUMNS if column not in target_to_source
    ]
    if duplicate_selected_sources:
        return
    if selected_supplier_name == "":
        st.info(
            f'V\u00e4lj "{SUPPLIER_HICORE_SUPPLIER_COLUMN}" fr\u00e5n leverant\u00f6rslistan f\u00f6r att skapa exportfilen.'
        )
        return
    if not target_to_source:
        st.info("Matcha minst en HiCore-kolumn f\u00f6r att skapa exportfilen.")
        return
    if missing_target_columns:
        st.info(
            "Omatchade HiCore-kolumner tas inte med i exportfilen: "
            + ", ".join(missing_target_columns)
        )
    if (
        SUPPLIER_HICORE_SKU_COLUMN not in target_to_source
        and (strip_leading_zeros_from_sku or ignore_rows_missing_sku)
    ):
        st.info(
            f'SKU-reglerna används först när "{SUPPLIER_HICORE_SKU_COLUMN}" är mappad.'
        )

    try:
        renamed_df = _build_supplier_hicore_renamed_copy(
            df_supplier,
            target_to_source=target_to_source,
            supplier_name=selected_supplier_name,
            strip_leading_zeros_from_sku=strip_leading_zeros_from_sku,
            ignore_rows_missing_sku=ignore_rows_missing_sku,
        )
    except Exception as exc:
        st.error(str(exc))
        return

    profile_save_error: Optional[str] = None
    profile_save_success: Optional[str] = None
    current_profile_mapping = {
        target_column: target_to_source[target_column]
        for target_column in SUPPLIER_HICORE_RENAME_COLUMNS
        if target_column in target_to_source
    }
    current_profile_options = _normalize_supplier_transform_profile_options(
        {
            SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS: strip_leading_zeros_from_sku,
            SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU: ignore_rows_missing_sku,
        }
    )
    has_saved_complete_profile = (
        saved_profile == current_profile_mapping
        and saved_profile_options == current_profile_options
    )
    save_profile_label = (
        "Uppdatera profil"
        if selected_supplier_name in supplier_transform_profiles
        else "Spara profil"
    )
    if has_saved_complete_profile and selected_supplier_name != "":
        st.caption("Aktuell kolumnmappning och SKU-regler matchar den sparade profilen.")

    if st.button(
        save_profile_label,
        type="secondary",
        key=f"save_supplier_transform_profile_{file_token}",
    ):
        profile_save_error = _persist_supplier_transform_profile(
            supplier_name=selected_supplier_name,
            target_to_source=current_profile_mapping,
            options=current_profile_options,
        )
        if profile_save_error is None:
            profile_save_success = f'Profil sparad för "{selected_supplier_name}".'
            saved_profile = dict(current_profile_mapping)
            saved_profile_options = dict(current_profile_options)
            supplier_transform_profiles = st.session_state.get("supplier_transform_profiles", {})

    if profile_save_error:
        st.error(profile_save_error)
    if profile_save_success:
        st.success(profile_save_success)

    mapping_rows = [
        {
            "HiCore-kolumn": target_column,
            "Leverant\u00f6rskolumn": target_to_source[target_column],
        }
        for target_column in SUPPLIER_HICORE_RENAME_COLUMNS
        if target_column in target_to_source
    ]
    mapping_rows.append(
        {
            "HiCore-kolumn": SUPPLIER_HICORE_SUPPLIER_COLUMN,
            "Leverant\u00f6rskolumn": f"V\u00e4rde fr\u00e5n supplier_index: {selected_supplier_name}",
        }
    )
    if missing_target_columns:
        st.success(
            "Delvis kolumnmappning klar. Omatchade HiCore-kolumner utel\u00e4mnas i exportfilen."
        )
    else:
        st.success("Kolumnmappningen \u00e4r komplett. Exportfilen \u00e4r klar.")
    st.caption(
        "SKU-regler i exporten: "
        f"ta bort inledande nollor = {'Ja' if strip_leading_zeros_from_sku else 'Nej'}, "
        f"ignorera rader utan SKU = {'Ja' if ignore_rows_missing_sku else 'Nej'}."
    )
    st.dataframe(pd.DataFrame(mapping_rows), use_container_width=True)

    preview_rows = min(len(renamed_df), 20)
    st.caption(f"F\u00f6rhandsvisning av resultatet ({preview_rows} f\u00f6rsta raderna)")
    st.dataframe(renamed_df.head(preview_rows), use_container_width=True)

    export_file_name = f"{Path(supplier_file_name).stem}_hicore_kolumnnamn.xlsx"
    st.download_button(
        label="Ladda ner ombyggd leverant\u00f6rsfil (Excel)",
        data=_df_excel_bytes(renamed_df, sheet_name="HiCore-format"),
        file_name=export_file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"download_supplier_hicore_renamed_{file_token}",
    )


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
            "Öppna profil",
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
