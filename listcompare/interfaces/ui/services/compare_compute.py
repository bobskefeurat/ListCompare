from __future__ import annotations

from typing import Optional

import pandas as pd

from ....core.comparison.use_cases import (
    build_comparison_results,
    unique_sorted_skus_from_mismatch_side,
    unique_sorted_skus_from_product_map,
)
from ....core.orders.web_order_compare import build_magento_only_web_orders_result
from ....core.products.product_mapping import prepare_data
from ..common import CompareUiResult, WebOrderCompareUiResult
from ..compute_shared import (
    ProgressCallback,
    _notify_progress,
)
from ..io.brand_filter import _normalized_skus_for_excluded_brands
from ..io.exports import _df_csv_bytes, _sku_csv_bytes
from ..io.tables import _mismatch_map_to_df, _product_map_to_df
from ..io.uploads import _read_compare_magento_csv_upload, _uploaded_csv_to_df


def compute_compare_result(
    hicore_bytes: bytes,
    magento_bytes: bytes,
    *,
    excluded_brands: Optional[list[str]] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> CompareUiResult:
    _notify_progress(progress_callback, 0.05, "Läser HiCore-fil")
    df_hicore = _uploaded_csv_to_df(hicore_bytes, sep=";")
    _notify_progress(progress_callback, 0.20, "Läser Magento-fil")
    df_magento = _read_compare_magento_csv_upload(magento_bytes)
    _notify_progress(progress_callback, 0.40, "Förbereder produktdata")
    hicore_map, magento_map = prepare_data(df_hicore, df_magento)
    _notify_progress(progress_callback, 0.55, "Filtrerar exkluderade varumärken")
    excluded_normalized_skus, warning_message = _normalized_skus_for_excluded_brands(
        df_hicore,
        excluded_brands or [],
    )

    _notify_progress(progress_callback, 0.75, "Jämför produkter")
    results = build_comparison_results(
        hicore_map,
        magento_map,
        excluded_normalized_skus=excluded_normalized_skus,
    )

    _notify_progress(progress_callback, 0.90, "Bygger export och förhandsvisning")
    only_in_magento_skus = unique_sorted_skus_from_product_map(results.only_in_magento)
    stock_skus = unique_sorted_skus_from_mismatch_side(results.stock_mismatches, "magento")
    result = CompareUiResult(
        only_in_magento_df=_product_map_to_df(results.only_in_magento),
        stock_mismatch_df=_mismatch_map_to_df(results.stock_mismatches),
        only_in_magento_csv_bytes=_sku_csv_bytes(only_in_magento_skus),
        stock_mismatch_csv_bytes=_sku_csv_bytes(stock_skus),
        only_in_magento_count=len(results.only_in_magento),
        stock_mismatch_count=len(results.stock_mismatches),
        warning_message=warning_message,
    )
    _notify_progress(progress_callback, 1.0, "Klar")
    return result


def compute_web_order_compare_result(
    hicore_bytes: bytes,
    magento_bytes: bytes,
    *,
    progress_callback: Optional[ProgressCallback] = None,
) -> WebOrderCompareUiResult:
    _notify_progress(progress_callback, 0.10, "Läser HiCore-fil")
    df_hicore = _uploaded_csv_to_df(hicore_bytes, sep=";")
    _notify_progress(progress_callback, 0.35, "Läser Magento-fil")
    df_magento = _read_compare_magento_csv_upload(magento_bytes)
    _notify_progress(progress_callback, 0.75, "Jämför webborder")
    web_order_results = build_magento_only_web_orders_result(df_hicore, df_magento)
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
