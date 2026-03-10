from __future__ import annotations

from typing import Optional

import pandas as pd

from ....core.products.product_filters import normalized_skus_from_brand_filter
from ....core.products.product_schema import HICORE_COLUMNS
from .index_names import _normalize_supplier_names


def _normalized_skus_for_excluded_brands(
    df_hicore: pd.DataFrame,
    excluded_brands: list[str],
) -> tuple[set[str], Optional[str]]:
    selected_brands = _normalize_supplier_names(excluded_brands)
    if not selected_brands:
        return set(), None

    brand_col = HICORE_COLUMNS.get("brand")
    sku_col = HICORE_COLUMNS["sku"]
    excluded_normalized_skus, missing_brand_column = normalized_skus_from_brand_filter(
        df_hicore,
        selected_brands=selected_brands,
        brand_column=brand_col,
        sku_column=sku_col,
    )
    if missing_brand_column:
        return (
            set(),
            'HiCore-filen saknar kolumnen "Varum\u00e4rke". Varum\u00e4rkesexkludering ignorerades.',
        )
    return excluded_normalized_skus, None

