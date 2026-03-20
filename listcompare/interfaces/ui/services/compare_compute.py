"""UI-facing compare result shaping and export assembly."""

from __future__ import annotations

from typing import Optional

import pandas as pd

from ..common import CompareUiResult, WebOrderCompareUiResult
from ..compute_shared import ProgressCallback, _notify_progress
from ..io.exports import _df_csv_bytes, _sku_csv_bytes
from ..io.tables import _mismatch_map_to_df, _product_map_to_df
from .compare_pipeline import (
    build_compare_artifacts,
    build_web_order_compare_artifacts,
    load_hicore_compare_df,
    load_magento_compare_df,
)


def compute_compare_result(
    hicore_bytes: bytes,
    magento_bytes: bytes,
    *,
    excluded_brands: Optional[list[str]] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> CompareUiResult:
    """Compute the main HiCore-Magento compare previews and CSV exports."""

    _notify_progress(progress_callback, 0.05, "Läser HiCore-fil")
    df_hicore = load_hicore_compare_df(hicore_bytes)
    _notify_progress(progress_callback, 0.20, "Läser Magento-fil")
    df_magento = load_magento_compare_df(magento_bytes)
    _notify_progress(progress_callback, 0.40, "Bygger compare-underlag")
    _notify_progress(progress_callback, 0.75, "Jämför produkter")
    artifacts = build_compare_artifacts(
        df_hicore,
        df_magento,
        excluded_brands=excluded_brands,
    )
    results = artifacts.comparison_results

    _notify_progress(progress_callback, 0.90, "Bygger export och förhandsvisning")
    result = CompareUiResult(
        only_in_magento_df=_product_map_to_df(results.only_in_magento),
        only_in_hicore_web_visible_in_stock_df=artifacts.only_in_hicore_web_visible_in_stock_df,
        stock_mismatch_df=_mismatch_map_to_df(results.stock_mismatches),
        only_in_magento_csv_bytes=_sku_csv_bytes(artifacts.only_in_magento_skus),
        only_in_hicore_web_visible_in_stock_csv_bytes=_sku_csv_bytes(
            artifacts.only_in_hicore_web_visible_in_stock_skus
        ),
        stock_mismatch_csv_bytes=_sku_csv_bytes(artifacts.stock_skus),
        only_in_magento_count=len(results.only_in_magento),
        only_in_hicore_web_visible_in_stock_count=len(
            artifacts.only_in_hicore_web_visible_in_stock_skus
        ),
        stock_mismatch_count=len(results.stock_mismatches),
        warning_message=artifacts.warning_message,
    )
    _notify_progress(progress_callback, 1.0, "Klar")
    return result


def compute_web_order_compare_result(
    hicore_bytes: bytes,
    magento_bytes: bytes,
    *,
    progress_callback: Optional[ProgressCallback] = None,
) -> WebOrderCompareUiResult:
    """Compute the Magento-only web-order export and preview table."""

    _notify_progress(progress_callback, 0.10, "Läser HiCore-fil")
    df_hicore = load_hicore_compare_df(hicore_bytes)
    _notify_progress(progress_callback, 0.35, "Läser Magento-fil")
    df_magento = load_magento_compare_df(magento_bytes)
    _notify_progress(progress_callback, 0.75, "Jämför webborder")
    web_order_results = build_web_order_compare_artifacts(df_hicore, df_magento)
    export_df = pd.DataFrame(
        {web_order_results.export_column_name: web_order_results.export_order_numbers}
    )
    result = WebOrderCompareUiResult(
        magento_only_web_orders_df=web_order_results.preview_df,
        magento_only_web_orders_csv_bytes=_df_csv_bytes(export_df),
        magento_only_web_orders_count=len(web_order_results.export_order_numbers),
        warning_message=web_order_results.warning_message,
    )
    _notify_progress(progress_callback, 1.0, "Klar")
    return result
