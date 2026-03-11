from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

import pandas as pd

from ....core.comparison.use_cases import (
    build_comparison_results,
    unique_sorted_skus_from_mismatch_side,
    unique_sorted_skus_from_product_map,
)
from ....core.orders.web_order_compare import build_magento_only_web_orders_result
from ....core.products.product_diff import normalize_sku
from ....core.products.product_mapping import prepare_data
from ....core.products.product_normalization import compute_hicore_stock, normalise_price, to_str
from ....core.products.product_schema import HICORE_COLUMNS
from ..common import CompareUiResult, WebOrderCompareUiResult
from ..compute_shared import (
    ProgressCallback,
    _notify_progress,
)
from ..io.brand_filter import _normalized_skus_for_excluded_brands
from ..io.exports import _df_csv_bytes, _sku_csv_bytes
from ..io.tables import _mismatch_map_to_df, _product_map_to_df
from ..io.uploads import _read_compare_magento_csv_upload, _uploaded_csv_to_df


def _is_truthy_web_flag(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().casefold() in {"1", "true", "yes", "ja", "on"}


def _parse_decimal(value: object) -> Optional[Decimal]:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text == "":
        return None
    normalized = text.replace(" ", "").replace("\u00a0", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except (InvalidOperation, ValueError):
        return None


def _empty_only_in_hicore_web_visible_df() -> pd.DataFrame:
    return pd.DataFrame(columns=["map_key", "sku", "name", "stock", "price", "supplier", "source"])


def _combine_warning_messages(*messages: Optional[str]) -> Optional[str]:
    seen: set[str] = set()
    combined: list[str] = []
    for raw_message in messages:
        message = str(raw_message).strip() if raw_message is not None else ""
        if message == "" or message in seen:
            continue
        seen.add(message)
        combined.append(message)
    if not combined:
        return None
    return "\n".join(combined)


def _only_in_hicore_web_visible_in_stock_df(
    df_hicore: pd.DataFrame,
    *,
    only_in_hicore_normalized_skus: set[str],
) -> tuple[pd.DataFrame, Optional[str]]:
    if not only_in_hicore_normalized_skus:
        return _empty_only_in_hicore_web_visible_df(), None

    sku_col = HICORE_COLUMNS["sku"]
    name_col = HICORE_COLUMNS["name"]
    price_col = HICORE_COLUMNS["price"]
    supplier_col = HICORE_COLUMNS["supplier"]
    show_on_web_col = HICORE_COLUMNS["show_on_web"]
    total_col = HICORE_COLUMNS["total_stock"]
    reserved_col = HICORE_COLUMNS["reserved"]

    if show_on_web_col not in df_hicore.columns:
        return (
            _empty_only_in_hicore_web_visible_df(),
            f'HiCore-filen saknar kolumnen "{show_on_web_col}". Den nya HiCore-fliken kunde inte beräknas.',
        )

    rows: list[dict[str, str]] = []
    for _, raw_row in df_hicore.iterrows():
        sku = to_str(raw_row.get(sku_col, ""))
        if sku == "" or normalize_sku(sku) not in only_in_hicore_normalized_skus:
            continue
        if not _is_truthy_web_flag(raw_row.get(show_on_web_col, "")):
            continue

        computed_stock = compute_hicore_stock(
            raw_row.get(total_col, ""),
            raw_row.get(reserved_col, ""),
        )
        parsed_stock = _parse_decimal(computed_stock)
        if parsed_stock is None or parsed_stock <= 0:
            continue

        rows.append(
            {
                "map_key": sku,
                "sku": sku,
                "name": to_str(raw_row.get(name_col, "")),
                "stock": computed_stock,
                "price": normalise_price(raw_row.get(price_col, "")),
                "supplier": to_str(raw_row.get(supplier_col, "")),
                "source": "hicore",
            }
        )

    if not rows:
        return _empty_only_in_hicore_web_visible_df(), None

    df = pd.DataFrame(rows)
    df["_lc_sort_sku"] = df["sku"].map(lambda value: normalize_sku(str(value).strip()))
    df["_lc_sort_sku_raw"] = df["sku"].map(lambda value: str(value).strip())
    df = df.sort_values(by=["_lc_sort_sku", "_lc_sort_sku_raw"], kind="stable")
    df = df.drop(columns=["_lc_sort_sku", "_lc_sort_sku_raw"])
    return df.reset_index(drop=True), None


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
    only_in_hicore_normalized_skus = {
        normalize_sku(str(sku))
        for sku in unique_sorted_skus_from_product_map(results.only_in_hicore)
        if normalize_sku(str(sku)) != ""
    }
    only_in_hicore_web_visible_in_stock_df, hicore_tab_warning = (
        _only_in_hicore_web_visible_in_stock_df(
            df_hicore,
            only_in_hicore_normalized_skus=only_in_hicore_normalized_skus,
        )
    )
    only_in_hicore_web_visible_in_stock_skus = sorted(
        {
            str(sku).strip()
            for sku in only_in_hicore_web_visible_in_stock_df["sku"].tolist()
            if str(sku).strip() != ""
        },
        key=lambda sku: (normalize_sku(str(sku)), str(sku)),
    )
    stock_skus = unique_sorted_skus_from_mismatch_side(results.stock_mismatches, "magento")
    result = CompareUiResult(
        only_in_magento_df=_product_map_to_df(results.only_in_magento),
        only_in_hicore_web_visible_in_stock_df=only_in_hicore_web_visible_in_stock_df,
        stock_mismatch_df=_mismatch_map_to_df(results.stock_mismatches),
        only_in_magento_csv_bytes=_sku_csv_bytes(only_in_magento_skus),
        only_in_hicore_web_visible_in_stock_csv_bytes=_sku_csv_bytes(
            only_in_hicore_web_visible_in_stock_skus
        ),
        stock_mismatch_csv_bytes=_sku_csv_bytes(stock_skus),
        only_in_magento_count=len(results.only_in_magento),
        only_in_hicore_web_visible_in_stock_count=len(only_in_hicore_web_visible_in_stock_skus),
        stock_mismatch_count=len(results.stock_mismatches),
        warning_message=_combine_warning_messages(warning_message, hicore_tab_warning),
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
