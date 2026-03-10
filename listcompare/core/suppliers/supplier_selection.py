from __future__ import annotations

import pandas as pd

from ..products.product_diff import ProductMap, normalize_sku


def _to_clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.casefold() == "nan":
        return ""
    return text


def filter_rows_by_normalized_skus(
    df_supplier: pd.DataFrame,
    *,
    sku_column: str,
    normalized_skus: set[str],
) -> pd.DataFrame:
    if sku_column not in df_supplier.columns or not normalized_skus:
        return df_supplier.iloc[0:0].copy()

    normalized_series = df_supplier[sku_column].map(
        lambda value: normalize_sku(_to_clean_text(value))
    )
    return df_supplier.loc[normalized_series.isin(normalized_skus)].copy()


def normalized_skus_from_product_map(product_map: ProductMap) -> set[str]:
    normalized_skus: set[str] = set()
    for sku in product_map.keys():
        normalized = normalize_sku(str(sku))
        if normalized != "":
            normalized_skus.add(normalized)
    return normalized_skus
