from __future__ import annotations

from collections.abc import Callable
from typing import Optional

import pandas as pd

from ...core.comparison_use_cases import (
    build_comparison_results,
    build_supplier_comparison_results,
    unique_sorted_skus_from_mismatch_side,
    unique_sorted_skus_from_product_map,
)
from ...core.product_diff import ProductMap, normalize_sku
from ...core.product_model import HICORE_COLUMNS, build_product_map, prepare_data
from ...core.supplier_products import (
    build_supplier_map,
    find_supplier_id_column,
    find_supplier_price_column,
)
from ..supplier_profile_utils import SUPPLIER_HICORE_RENAME_COLUMNS
from .common import CompareUiResult, SupplierUiResult, WebOrderCompareUiResult
from .data_io import (
    _df_csv_bytes,
    _df_excel_bytes,
    _mismatch_map_to_df,
    _read_compare_magento_csv_upload,
    _normalized_skus_for_excluded_brands,
    _product_map_to_df,
    _sku_csv_bytes,
    _uploaded_csv_to_df,
)

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
        if cleaned.casefold() == "ink\u00f6pspris".casefold():
            return cleaned
    return "Ink\u00f6pspris"


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


def _filter_rows_by_normalized_skus(
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


def _normalized_skus_from_product_map(product_map: ProductMap) -> set[str]:
    normalized_skus: set[str] = set()
    for sku in product_map.keys():
        normalized = normalize_sku(str(sku))
        if normalized != "":
            normalized_skus.add(normalized)
    return normalized_skus


def _build_supplier_price_export_df(
    df_supplier: pd.DataFrame,
    *,
    id_column: str,
    price_column: str,
    purchase_column: Optional[str],
    normalized_skus: set[str],
    include_purchase: bool,
) -> pd.DataFrame:
    sku_column_name = HICORE_COLUMNS["sku"]
    price_column_name = HICORE_COLUMNS["price"]
    purchase_column_name = _hicore_purchase_column_name()
    export_columns = [sku_column_name]
    if include_purchase:
        export_columns.append(purchase_column_name)
    export_columns.append(price_column_name)

    filtered_rows = _filter_rows_by_normalized_skus(
        df_supplier,
        sku_column=id_column,
        normalized_skus=normalized_skus,
    )
    if filtered_rows.empty:
        return pd.DataFrame(columns=export_columns)

    export_df = pd.DataFrame()
    export_df[sku_column_name] = filtered_rows[id_column].map(_to_clean_text)
    if include_purchase:
        if purchase_column is not None and purchase_column in filtered_rows.columns:
            export_df[purchase_column_name] = filtered_rows[purchase_column].map(_to_clean_text)
        else:
            export_df[purchase_column_name] = ""
    export_df[price_column_name] = filtered_rows[price_column].map(_to_clean_text)
    return _sort_df_by_sku_column(export_df, sku_column=sku_column_name)


def _compute_compare_result(
    hicore_bytes: bytes,
    magento_bytes: bytes,
    *,
    excluded_brands: Optional[list[str]] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> CompareUiResult:
    _notify_progress(progress_callback, 0.05, "L\u00e4ser HiCore-fil")
    df_hicore = _uploaded_csv_to_df(hicore_bytes, sep=";")
    _notify_progress(progress_callback, 0.20, "L\u00e4ser Magento-fil")
    df_magento = _read_compare_magento_csv_upload(magento_bytes)
    _notify_progress(progress_callback, 0.40, "F\u00f6rbereder produktdata")
    hicore_map, magento_map = prepare_data(df_hicore, df_magento)
    _notify_progress(progress_callback, 0.55, "Filtrerar exkluderade varum\u00e4rken")
    excluded_normalized_skus, warning_message = _normalized_skus_for_excluded_brands(
        df_hicore,
        excluded_brands or [],
    )

    _notify_progress(progress_callback, 0.75, "J\u00e4mf\u00f6r produkter")
    results = build_comparison_results(
        hicore_map,
        magento_map,
        excluded_normalized_skus=excluded_normalized_skus,
    )

    _notify_progress(progress_callback, 0.90, "Bygger export och f\u00f6rhandsvisning")
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
    _notify_progress(progress_callback, 0.10, "L\u00e4ser HiCore-fil")
    df_hicore = _uploaded_csv_to_df(hicore_bytes, sep=";")
    _notify_progress(progress_callback, 0.35, "L\u00e4ser Magento-fil")
    df_magento = _read_compare_magento_csv_upload(magento_bytes)
    _notify_progress(progress_callback, 0.75, "J\u00e4mf\u00f6r webborder")
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


def _compute_supplier_result(
    hicore_bytes: bytes,
    *,
    supplier_name: str,
    supplier_df: pd.DataFrame,
    excluded_brands: Optional[list[str]] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> SupplierUiResult:
    _notify_progress(progress_callback, 0.05, "L\u00e4ser HiCore-fil")
    df_hicore = _uploaded_csv_to_df(hicore_bytes, sep=";")
    _notify_progress(progress_callback, 0.15, "Bygger HiCore-karta")
    hicore_map = build_product_map(
        df_hicore,
        source="hicore",
        columns=HICORE_COLUMNS,
    )
    _notify_progress(progress_callback, 0.25, "Filtrerar exkluderade varum\u00e4rken")
    excluded_normalized_skus, warning_message = _normalized_skus_for_excluded_brands(
        df_hicore,
        excluded_brands or [],
    )
    _notify_progress(progress_callback, 0.35, "F\u00f6rbereder leverant\u00f6rsdata")
    df_supplier = supplier_df.copy()
    supplier_source_columns = [str(column).strip() for column in df_supplier.columns]
    id_column = find_supplier_id_column(df_supplier)
    price_column = find_supplier_price_column(df_supplier)
    purchase_column = _find_case_insensitive_column(
        supplier_source_columns,
        _hicore_purchase_column_name(),
    )
    _notify_progress(progress_callback, 0.50, "Bygger leverant\u00f6rskarta")
    supplier_map = build_supplier_map(df_supplier)
    _notify_progress(progress_callback, 0.62, "J\u00e4mf\u00f6r mot HiCore")
    results = build_supplier_comparison_results(
        hicore_map,
        supplier_map,
        supplier_internal_name=supplier_name,
        excluded_normalized_skus=excluded_normalized_skus,
    )

    _notify_progress(progress_callback, 0.74, "Bygger export f\u00f6r utg\u00e5ende och nyheter")
    outgoing_skus = unique_sorted_skus_from_product_map(results.outgoing)
    outgoing_export_df = pd.DataFrame(
        {
            HICORE_COLUMNS["sku"]: sorted(
                {sku for sku in outgoing_skus if str(sku).strip() != ""},
                key=lambda sku: (normalize_sku(str(sku)), str(sku)),
            )
        }
    )

    new_products_normalized_skus = _normalized_skus_from_product_map(results.new_products)
    new_products_export_df = _sort_df_by_sku_column(
        _filter_rows_by_normalized_skus(
            df_supplier,
            sku_column=id_column,
            normalized_skus=new_products_normalized_skus,
        ),
        sku_column=id_column,
    )

    _notify_progress(progress_callback, 0.86, "Bygger export f\u00f6r prisuppdateringar")
    out_of_stock_normalized_skus = set(results.price_updates_out_of_stock.keys())
    in_stock_normalized_skus = set(results.price_updates_in_stock.keys())
    price_updates_out_of_stock_export_df = _build_supplier_price_export_df(
        df_supplier,
        id_column=id_column,
        price_column=price_column,
        purchase_column=purchase_column,
        normalized_skus=out_of_stock_normalized_skus,
        include_purchase=True,
    )
    price_updates_in_stock_export_df = _build_supplier_price_export_df(
        df_supplier,
        id_column=id_column,
        price_column=price_column,
        purchase_column=purchase_column,
        normalized_skus=in_stock_normalized_skus,
        include_purchase=False,
    )

    _notify_progress(progress_callback, 0.95, "Skapar Excelfiler")
    result = SupplierUiResult(
        outgoing_df=_product_map_to_df(results.outgoing),
        new_products_df=_product_map_to_df(results.new_products),
        price_updates_out_of_stock_df=_mismatch_map_to_df(
            results.price_updates_out_of_stock,
            preferred_side_order=("hicore", "supplier"),
        ),
        price_updates_in_stock_df=_mismatch_map_to_df(
            results.price_updates_in_stock,
            preferred_side_order=("hicore", "supplier"),
        ),
        outgoing_excel_bytes=_df_excel_bytes(outgoing_export_df, sheet_name="Utgående"),
        new_products_excel_bytes=_df_excel_bytes(new_products_export_df, sheet_name="Nyheter"),
        price_updates_out_of_stock_excel_bytes=_df_excel_bytes(
            price_updates_out_of_stock_export_df,
            sheet_name="Prisuppdatering, Ej i lager",
        ),
        price_updates_in_stock_excel_bytes=_df_excel_bytes(
            price_updates_in_stock_export_df,
            sheet_name="Prisuppdatering, I lager",
        ),
        outgoing_count=len(results.outgoing),
        new_products_count=len(results.new_products),
        price_updates_out_of_stock_count=len(results.price_updates_out_of_stock),
        price_updates_in_stock_count=len(results.price_updates_in_stock),
        warning_message=warning_message,
    )
    _notify_progress(progress_callback, 1.0, "Klar")
    return result
