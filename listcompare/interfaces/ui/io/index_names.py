from __future__ import annotations

from pathlib import Path
from typing import Optional

import streamlit as st

from ..persistence import index_store as _index_store
from .uploads import _read_hicore_name_columns


def _normalize_supplier_names(raw_names: list[str]) -> list[str]:
    return _index_store.normalize_names(raw_names)


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
    supplier_names, brand_names, has_supplier_column, has_brand_column = (
        _read_hicore_name_columns(uploaded_name, uploaded_bytes)
    )
    return (
        _normalize_supplier_names(supplier_names),
        _normalize_supplier_names(brand_names),
        has_supplier_column,
        has_brand_column,
    )
