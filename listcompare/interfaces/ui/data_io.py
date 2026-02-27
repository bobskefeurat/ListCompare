from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from ...core.product_diff import ProductMap, normalize_sku
from ...core.product_model import HICORE_COLUMNS, Product
from .common import CSV_ENCODINGS
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


