from __future__ import annotations

from typing import Optional

import pandas as pd

from ...core.comparison_use_cases import (
    build_comparison_results,
    unique_sorted_skus_from_mismatch_side,
    unique_sorted_skus_from_product_map,
)
from ...core.product_mapping import prepare_data
from .common import CompareUiResult, WebOrderCompareUiResult
from .compute_shared import (
    ProgressCallback,
    _find_case_insensitive_column,
    _notify_progress,
    _to_clean_text,
)
from .data_io import (
    _df_csv_bytes,
    _mismatch_map_to_df,
    _normalized_skus_for_excluded_brands,
    _product_map_to_df,
    _read_compare_magento_csv_upload,
    _sku_csv_bytes,
    _uploaded_csv_to_df,
)


def _normalize_order_number(value: object) -> str:
    text = _to_clean_text(value)
    if text == "":
        return ""
    return text.lstrip("0")


def _empty_web_order_export_bytes() -> bytes:
    return _df_csv_bytes(pd.DataFrame({"ID": []}))


def _build_magento_only_web_orders_result(
    df_hicore: pd.DataFrame,
    df_magento: pd.DataFrame,
) -> tuple[pd.DataFrame, bytes, int, Optional[str]]:
    hicore_column = _find_case_insensitive_column(df_hicore.columns.tolist(), "Webbordernr")
    if hicore_column is None:
        return (
            pd.DataFrame(columns=df_magento.columns.tolist()),
            _empty_web_order_export_bytes(),
            0,
            'HiCore-filen saknar kolumnen "Webbordernr".',
        )

    magento_column = _find_case_insensitive_column(df_magento.columns.tolist(), "ID")
    if magento_column is None:
        return (
            pd.DataFrame(columns=df_magento.columns.tolist()),
            _empty_web_order_export_bytes(),
            0,
            'Magento-filen saknar kolumnen "ID".',
        )

    hicore_order_numbers = {
        normalized
        for normalized in df_hicore[hicore_column].map(_normalize_order_number).tolist()
        if normalized != ""
    }
    normalized_magento_order_numbers = df_magento[magento_column].map(_normalize_order_number)
    missing_order_mask = normalized_magento_order_numbers.map(
        lambda value: value != "" and value not in hicore_order_numbers
    )
    preview_df = df_magento.loc[missing_order_mask].copy().reset_index(drop=True)

    seen_normalized_order_numbers: set[str] = set()
    export_order_numbers: list[str] = []
    for raw_order_number, normalized_order_number in zip(
        df_magento[magento_column].tolist(),
        normalized_magento_order_numbers.tolist(),
    ):
        if normalized_order_number == "":
            continue
        if normalized_order_number in hicore_order_numbers:
            continue
        if normalized_order_number in seen_normalized_order_numbers:
            continue
        seen_normalized_order_numbers.add(normalized_order_number)
        export_order_numbers.append(_to_clean_text(raw_order_number))

    export_df = pd.DataFrame({magento_column: export_order_numbers})
    return (
        preview_df,
        _df_csv_bytes(export_df),
        len(export_order_numbers),
        None,
    )


def _compute_compare_result(
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


def _compute_web_order_compare_result(
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
    (
        magento_only_web_orders_df,
        magento_only_web_orders_csv_bytes,
        magento_only_web_orders_count,
        warning_message,
    ) = _build_magento_only_web_orders_result(df_hicore, df_magento)
    result = WebOrderCompareUiResult(
        magento_only_web_orders_df=magento_only_web_orders_df,
        magento_only_web_orders_csv_bytes=magento_only_web_orders_csv_bytes,
        magento_only_web_orders_count=magento_only_web_orders_count,
        warning_message=warning_message,
    )
    _notify_progress(progress_callback, 1.0, "Klar")
    return result
