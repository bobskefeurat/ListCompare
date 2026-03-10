from __future__ import annotations

from collections.abc import Callable
from typing import Optional

import pandas as pd

from ...core.products.product_diff import normalize_sku
from ...core.suppliers.profile import SUPPLIER_HICORE_RENAME_COLUMNS

ProgressCallback = Callable[[float, str], None]


def _notify_progress(
    progress_callback: Optional[ProgressCallback],
    progress: float,
    message: str,
) -> None:
    if progress_callback is None:
        return
    clamped_progress = max(0.0, min(1.0, float(progress)))
    progress_callback(clamped_progress, message)


def _to_clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.casefold() == "nan":
        return ""
    return text


def _find_case_insensitive_column(columns: list[str], wanted: str) -> Optional[str]:
    wanted_folded = str(wanted).strip().casefold()
    for column in columns:
        if str(column).strip().casefold() == wanted_folded:
            return str(column)
    return None


def _hicore_purchase_column_name() -> str:
    for column_name in SUPPLIER_HICORE_RENAME_COLUMNS:
        cleaned = str(column_name).strip()
        if cleaned.casefold() == "inköpspris".casefold():
            return cleaned
    return "Inköpspris"


def _sort_df_by_sku_column(df: pd.DataFrame, *, sku_column: str) -> pd.DataFrame:
    if df.empty or sku_column not in df.columns:
        return df.reset_index(drop=True)

    sorted_df = df.copy()
    sorted_df["_lc_sort_sku"] = sorted_df[sku_column].map(
        lambda value: normalize_sku(_to_clean_text(value))
    )
    sorted_df["_lc_sort_sku_raw"] = sorted_df[sku_column].map(_to_clean_text)
    sorted_df = sorted_df.sort_values(
        by=["_lc_sort_sku", "_lc_sort_sku_raw"],
        kind="stable",
    )
    sorted_df = sorted_df.drop(columns=["_lc_sort_sku", "_lc_sort_sku_raw"])
    return sorted_df.reset_index(drop=True)

