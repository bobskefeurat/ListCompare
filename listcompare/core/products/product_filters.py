from __future__ import annotations

from typing import Optional

import pandas as pd

from .product_diff import normalize_sku


def normalized_skus_from_brand_filter(
    df_hicore: pd.DataFrame,
    *,
    selected_brands: list[str],
    brand_column: Optional[str],
    sku_column: str,
) -> tuple[set[str], bool]:
    if not selected_brands:
        return set(), False

    if brand_column is None or brand_column not in df_hicore.columns:
        return set(), True
    if sku_column not in df_hicore.columns:
        return set(), False

    selected_folded = {name.casefold() for name in selected_brands}
    excluded_normalized_skus: set[str] = set()
    for raw_brand, raw_sku in zip(
        df_hicore[brand_column].tolist(),
        df_hicore[sku_column].tolist(),
    ):
        if pd.isna(raw_brand):
            continue

        brand_name = str(raw_brand).strip()
        if brand_name == "" or brand_name.casefold() == "nan":
            continue
        if brand_name.casefold() not in selected_folded:
            continue

        if pd.isna(raw_sku):
            continue

        normalized = normalize_sku(str(raw_sku))
        if normalized != "":
            excluded_normalized_skus.add(normalized)

    return excluded_normalized_skus, False
