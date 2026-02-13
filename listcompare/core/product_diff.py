from __future__ import annotations
from typing import Dict, List, Tuple

from .product_model import Product

ProductMap = Dict[str, List[Product]]


def normalize_sku(sku: str) -> str:
    s = sku.strip()
    if s == "":
        return ""
    s2 = s.lstrip("0")
    return s2 if s2 != "" else "0"


def build_normalized_map(product_map: ProductMap) -> Dict[str, List[Product]]:
    out: Dict[str, List[Product]] = {}
    for sku, rows in product_map.items():
        key = normalize_sku(sku)
        out.setdefault(key, []).extend(rows)
    return out


def count_products(product_map: ProductMap) -> int:
    return sum(len(rows) for rows in product_map.values())


def list_duplicate_skus(product_map: ProductMap) -> ProductMap:
    return {sku: rows for sku, rows in product_map.items() if len(rows) > 1}


def list_empty_field_rows(product_map: ProductMap, *, field: str) -> List[Product]:
    if field not in {"sku", "name", "stock"}:
        raise ValueError(f"field must be one of: sku, name, stock. Got: {field}")

    out: List[Product] = []
    for rows in product_map.values():
        for p in rows:
            if getattr(p, field) == "":
                out.append(p)
    return out


def find_missing_products_by_sku(
    left_map: ProductMap,
    right_map: ProductMap,
) -> Tuple[ProductMap, ProductMap]:
    left_norm = set(build_normalized_map(left_map).keys())
    right_norm = set(build_normalized_map(right_map).keys())

    only_in_right: ProductMap = {}
    for right_sku, right_rows in right_map.items():
        if normalize_sku(right_sku) not in left_norm:
            only_in_right[right_sku] = right_rows

    only_in_left: ProductMap = {}
    for left_sku, left_rows in left_map.items():
        if normalize_sku(left_sku) not in right_norm:
            only_in_left[left_sku] = left_rows

    return only_in_left, only_in_right


def find_missing_skus(hicore_map: ProductMap, magento_map: ProductMap) -> Tuple[ProductMap, ProductMap]:
    # Backward-compatible alias for existing callers.
    return find_missing_products_by_sku(hicore_map, magento_map)


def find_field_mismatches_by_sku(
    hicore_map: ProductMap,
    magento_map: ProductMap,
    *,
    field: str,  # "name" | "stock"
) -> Dict[str, Dict[str, List[Product]]]:

    if field not in {"name", "stock"}:
        raise ValueError(f"field must be 'name' or 'stock'. Got: {field}")

    out: Dict[str, Dict[str, List[Product]]] = {}

    hicore_norm_map = build_normalized_map(hicore_map)
    magento_norm_map = build_normalized_map(magento_map)

    shared_keys = set(hicore_norm_map.keys()) & set(magento_norm_map.keys())

    for key in shared_keys:
        h_rows = hicore_norm_map[key]
        m_rows = magento_norm_map[key]

        h_values = {getattr(p, field) for p in h_rows}
        m_values = {getattr(p, field) for p in m_rows}

        if h_values != m_values:
            out[key] = {"hicore": h_rows, "magento": m_rows}

    return out
