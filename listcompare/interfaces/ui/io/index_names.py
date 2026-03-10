from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from ....core.products.product_schema import HICORE_COLUMNS
from ..persistence import index_store as _index_store
from .uploads import _uploaded_csv_to_df


def _normalize_supplier_names(raw_names: list[str]) -> list[str]:
    return _index_store.normalize_names(raw_names)


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
    return _index_store.load_suppliers_from_index(path)


def _save_suppliers_to_index(path: Path, suppliers: list[str]) -> None:
    _index_store.save_suppliers_to_index(path, suppliers)


def _load_brands_from_index(path: Path) -> tuple[list[str], Optional[str]]:
    return _index_store.load_brands_from_index(path)


def _save_brands_to_index(path: Path, brands: list[str]) -> None:
    _index_store.save_brands_to_index(path, brands)


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

