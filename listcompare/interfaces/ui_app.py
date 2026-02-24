from __future__ import annotations

import io
import json
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
from ..core.supplier_products import build_supplier_map

CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin1")
SUPPLIER_INDEX_PATH = (Path(__file__).resolve().parents[2] / "supplier_index.txt").resolve()
BRAND_INDEX_PATH = (Path(__file__).resolve().parents[2] / "brand_index.txt").resolve()
UI_SETTINGS_PATH = (Path(__file__).resolve().parents[2] / "ui_settings.json").resolve()


MENU_COMPARE = "J\u00e4mf\u00f6r Hicore/Magento"
MENU_SUPPLIER = "Hantera leverant\u00f6r"
MENU_SETTINGS = "Inst\u00e4llningar"

FILE_STATE_KEYS = {
    "hicore": "stored_hicore_file",
    "magento": "stored_magento_file",
    "supplier": "stored_supplier_file",
}

UPLOADER_KEYS_BY_KIND = {
    "hicore": ("compare_hicore_uploader", "supplier_hicore_uploader"),
    "magento": ("compare_magento_uploader",),
    "supplier": ("supplier_file_uploader",),
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
        "_last_supplier_internal_name": None,
        "ui_settings_load_error": ui_settings_error,
        "ui_settings_save_error": None,
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
            return pd.read_csv(io.StringIO(text), **kwargs)
        except UnicodeDecodeError as err:
            last_err = err
    if last_err is not None:
        raise last_err
    raise UnicodeDecodeError("utf-8", b"", 0, 1, "Unable to decode uploaded CSV")


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
        return _uploaded_csv_to_df(data, sep=None, engine="python")
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


def _sku_csv_bytes(skus: list[str]) -> bytes:
    df = pd.DataFrame({"Art.m\u00e4rkning": skus})
    return df.to_csv(sep=";", index=False).encode("utf-8-sig")


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
        st.dataframe(result.stock_mismatch_df, use_container_width=True)


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


def _render_supplier_page(
    *,
    supplier_options: list[str],
    supplier_index_error: Optional[str],
    new_supplier_names: list[str],
    excluded_brands: list[str],
) -> None:
    st.header(MENU_SUPPLIER)

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

    can_run = (
        hicore_file is not None
        and supplier_file is not None
        and supplier_internal_name is not None
        and str(supplier_internal_name).strip() != ""
    )
    if st.button(
        "K\u00f6r J\u00e4mf\u00f6relse",
        type="primary",
        disabled=not can_run,
        key="run_supplier_button",
    ):
        supplier_name = str(supplier_internal_name).strip()
        try:
            result = _compute_supplier_result(
                hicore_bytes=hicore_file["bytes"],  # type: ignore[index]
                supplier_name=supplier_name,
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
