from __future__ import annotations

import io
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
from ..core.product_model import HICORE_COLUMNS, Product, prepare_data
from ..core.supplier_products import build_supplier_map

CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin1")
SUPPLIER_INDEX_PATH = (Path(__file__).resolve().parents[2] / "supplier_index.txt").resolve()
BRAND_INDEX_PATH = (Path(__file__).resolve().parents[2] / "brand_index.txt").resolve()


@dataclass(frozen=True)
class UiResult:
    only_in_magento_df: pd.DataFrame
    stock_mismatch_df: pd.DataFrame
    internal_only_df: Optional[pd.DataFrame]
    stock_mismatch_csv_bytes: bytes
    internal_only_csv_bytes: Optional[bytes]
    only_in_magento_count: int
    stock_mismatch_count: int
    internal_only_count: Optional[int]
    warning_message: Optional[str]


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
        return [], f"Saknar leverantörsindex: {path.name}"

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
        return [], f"Saknar varumarkesindex: {path.name}"

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
        return set(), 'HiCore-filen saknar kolumnen "Varumärke". Varumärkesexkludering ignorerades.'

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
    df = pd.DataFrame({"Art.märkning": skus})
    return df.to_csv(sep=";", index=False).encode("utf-8-sig")


def _compute_ui_result(
    hicore_bytes: bytes,
    magento_bytes: bytes,
    supplier_name: str,
    supplier_file_name: Optional[str],
    supplier_bytes: Optional[bytes],
    excluded_brands: Optional[list[str]] = None,
) -> UiResult:
    df_hicore = _uploaded_csv_to_df(hicore_bytes, sep=";")
    df_magento = _uploaded_csv_to_df(magento_bytes, sep=";")
    hicore_map, magento_map = prepare_data(df_hicore, df_magento)
    excluded_normalized_skus, warning_message = _normalized_skus_for_excluded_brands(
        df_hicore,
        excluded_brands or [],
    )

    supplier_map: Optional[ProductMap] = None
    if supplier_file_name and supplier_bytes:
        df_supplier = _read_supplier_upload(supplier_file_name, supplier_bytes)
        supplier_map = build_supplier_map(df_supplier)

    results = build_comparison_results(
        hicore_map,
        magento_map,
        supplier_map=supplier_map,
        supplier_internal_name=supplier_name,
        excluded_normalized_skus=excluded_normalized_skus,
    )

    only_in_magento_df = _product_map_to_df(results.only_in_magento)
    stock_mismatch_df = _mismatch_map_to_df(results.stock_mismatches)
    internal_only_df = (
        _product_map_to_df(results.internal_only_candidates)
        if results.internal_only_candidates is not None
        else None
    )

    stock_skus = unique_sorted_skus_from_mismatch_side(results.stock_mismatches, "magento")
    stock_csv_bytes = _sku_csv_bytes(stock_skus)

    internal_only_csv_bytes: Optional[bytes] = None
    if results.internal_only_candidates is not None:
        internal_skus = unique_sorted_skus_from_product_map(results.internal_only_candidates)
        internal_only_csv_bytes = _sku_csv_bytes(internal_skus)

    return UiResult(
        only_in_magento_df=only_in_magento_df,
        stock_mismatch_df=stock_mismatch_df,
        internal_only_df=internal_only_df,
        stock_mismatch_csv_bytes=stock_csv_bytes,
        internal_only_csv_bytes=internal_only_csv_bytes,
        only_in_magento_count=len(results.only_in_magento),
        stock_mismatch_count=len(results.stock_mismatches),
        internal_only_count=(
            len(results.internal_only_candidates)
            if results.internal_only_candidates is not None
            else None
        ),
        warning_message=warning_message,
    )


def _render_results(result: UiResult) -> None:
    if result.warning_message:
        st.warning(result.warning_message)

    col1, col2, col3 = st.columns(3)
    col1.metric("Only in Magento", result.only_in_magento_count)
    col2.metric("Stock mismatches", result.stock_mismatch_count)
    col3.metric(
        "Internal only",
        result.internal_only_count if result.internal_only_count is not None else "N/A",
    )

    download_col1, download_col2 = st.columns(2)
    download_col1.download_button(
        label="Ladda ner stock_mismatch_skus.csv",
        data=result.stock_mismatch_csv_bytes,
        file_name="stock_mismatch_skus.csv",
        mime="text/csv",
    )
    if result.internal_only_csv_bytes is not None:
        download_col2.download_button(
            label="Ladda ner internal_only_skus.csv",
            data=result.internal_only_csv_bytes,
            file_name="internal_only_skus.csv",
            mime="text/csv",
        )

    tab1, tab2, tab3 = st.tabs(
        ["Only in Magento", "Stock mismatches", "Internal only (supplier)"]
    )
    with tab1:
        st.dataframe(result.only_in_magento_df, use_container_width=True)
    with tab2:
        st.dataframe(result.stock_mismatch_df, use_container_width=True)
    with tab3:
        if result.internal_only_df is None:
            st.info("Ingen supplier-fil uppladdad, så den här listan kan inte beräknas.")
        else:
            st.dataframe(result.internal_only_df, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="ListCompare", layout="wide")
    st.title("ListCompare")

    indexed_suppliers, supplier_index_error = _load_suppliers_from_index(SUPPLIER_INDEX_PATH)
    indexed_brands, brand_index_error = _load_brands_from_index(BRAND_INDEX_PATH)

    hicore_file = st.file_uploader(
        "HiCore-export (.csv)",
        type=["csv"],
        accept_multiple_files=False,
    )
    magento_file = st.file_uploader(
        "Magento-export (.csv)",
        type=["csv"],
        accept_multiple_files=False,
    )
    supplier_file = st.file_uploader(
        "Supplier-fil (.csv/.xlsx/.xls/.xlsm) - valfri",
        type=["csv", "xlsx", "xls", "xlsm"],
        accept_multiple_files=False,
    )

    supplier_options = indexed_suppliers
    brand_options = indexed_brands
    new_supplier_names: list[str] = []
    new_brand_names: list[str] = []
    hicore_missing_brand_column = False
    if hicore_file is not None:
        try:
            (
                uploaded_suppliers,
                uploaded_brands,
                _has_supplier_column,
                has_brand_column,
            ) = _load_names_from_uploaded_hicore(
                hicore_file.name,
                hicore_file.getvalue(),
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
            st.warning(f"Kunde inte läsa leverantörs-/varumärkeslista från uppladdad HiCore-fil: {exc}")

    scanned_supplier_count = len(supplier_options)
    supplier_internal_name = st.selectbox(
        "Leverantör",
        options=supplier_options,
        index=None,
        accept_new_options=True,
        placeholder="Välj leverantör...",
    )
    excluded_brands = st.multiselect(
        "Exkludera varumärken",
        options=brand_options,
        default=[],
        placeholder="Välj ett eller flera varumärken...",
        disabled=bool(hicore_file is not None and hicore_missing_brand_column),
    )

    st.caption(
        f"Antal leverantörer: {scanned_supplier_count}."
    )
    if new_supplier_names:
        st.success(
            f"Uppdaterade {SUPPLIER_INDEX_PATH.name} med {len(new_supplier_names)} ny(a) leverantör(er)."
        )
    if supplier_index_error:
        st.warning(
            f"Kunde inte läsa {SUPPLIER_INDEX_PATH.name} vid uppstart: {supplier_index_error}"
        )
    if hicore_file is not None and hicore_missing_brand_column:
        st.warning('HiCore-filen saknar kolumnen "Varumärke". Varumärkesexkludering är inte tillgänglig för denna fil.')

    st.caption(f"Antal varumärken: {len(brand_options)}.")
    if new_brand_names:
        st.success(
            f"Uppdaterade {BRAND_INDEX_PATH.name} med {len(new_brand_names)} ny(a) varumärke(n)."
        )
    if brand_index_error:
        st.warning(
            f"Kunde inte läsa {BRAND_INDEX_PATH.name} vid uppstart: {brand_index_error}"
        )

    if "ui_result" not in st.session_state:
        st.session_state["ui_result"] = None
    if "ui_error" not in st.session_state:
        st.session_state["ui_error"] = None

    if st.button("Kör jämförelse", type="primary"):
        if hicore_file is None or magento_file is None:
            st.session_state["ui_error"] = "Ladda upp både HiCore- och Magento-fil."
            st.session_state["ui_result"] = None
        elif supplier_internal_name is None or str(supplier_internal_name).strip() == "":
            st.session_state["ui_error"] = "Välj eller skriv ett leverantörsnamn."
            st.session_state["ui_result"] = None
        else:
            try:
                result = _compute_ui_result(
                    hicore_bytes=hicore_file.getvalue(),
                    magento_bytes=magento_file.getvalue(),
                    supplier_name=str(supplier_internal_name).strip(),
                    supplier_file_name=supplier_file.name if supplier_file else None,
                    supplier_bytes=supplier_file.getvalue() if supplier_file else None,
                    excluded_brands=[str(name) for name in excluded_brands],
                )
                st.session_state["ui_result"] = result
                st.session_state["ui_error"] = None
            except Exception as exc:
                st.session_state["ui_result"] = None
                st.session_state["ui_error"] = str(exc)

    if st.session_state["ui_error"]:
        st.error(st.session_state["ui_error"])

    if st.session_state["ui_result"] is not None:
        _render_results(st.session_state["ui_result"])


if __name__ == "__main__":
    main()
