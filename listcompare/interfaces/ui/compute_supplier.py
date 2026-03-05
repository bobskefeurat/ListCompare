from __future__ import annotations

from typing import Optional

import pandas as pd

from ...core.comparison_use_cases import (
    build_supplier_comparison_results,
    unique_sorted_skus_from_product_map,
)
from ...core.product_diff import ProductMap, normalize_sku
from ...core.product_mapping import build_product_map
from ...core.product_schema import HICORE_COLUMNS
from ...core.supplier_products import (
    build_supplier_map,
    find_supplier_id_column,
    find_supplier_price_column,
)
from .common import SupplierUiResult
from .compute_shared import (
    ProgressCallback,
    _find_case_insensitive_column,
    _hicore_purchase_column_name,
    _notify_progress,
    _sort_df_by_sku_column,
    _to_clean_text,
)
from .data_io import (
    _df_excel_bytes,
    _mismatch_map_to_df,
    _normalized_skus_for_excluded_brands,
    _product_map_to_df,
    _uploaded_csv_to_df,
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


def _compute_supplier_result(
    hicore_bytes: bytes,
    *,
    supplier_name: str,
    supplier_df: pd.DataFrame,
    excluded_brands: Optional[list[str]] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> SupplierUiResult:
    _notify_progress(progress_callback, 0.05, "Läser HiCore-fil")
    df_hicore = _uploaded_csv_to_df(hicore_bytes, sep=";")
    _notify_progress(progress_callback, 0.15, "Bygger HiCore-karta")
    hicore_map = build_product_map(
        df_hicore,
        source="hicore",
        columns=HICORE_COLUMNS,
    )
    _notify_progress(progress_callback, 0.25, "Filtrerar exkluderade varumärken")
    excluded_normalized_skus, warning_message = _normalized_skus_for_excluded_brands(
        df_hicore,
        excluded_brands or [],
    )
    _notify_progress(progress_callback, 0.35, "Förbereder leverantörsdata")
    df_supplier = supplier_df.copy()
    supplier_source_columns = [str(column).strip() for column in df_supplier.columns]
    id_column = find_supplier_id_column(df_supplier)
    price_column = find_supplier_price_column(df_supplier)
    purchase_column = _find_case_insensitive_column(
        supplier_source_columns,
        _hicore_purchase_column_name(),
    )
    _notify_progress(progress_callback, 0.50, "Bygger leverantörskarta")
    supplier_map = build_supplier_map(df_supplier)
    _notify_progress(progress_callback, 0.62, "Jämför mot HiCore")
    results = build_supplier_comparison_results(
        hicore_map,
        supplier_map,
        supplier_internal_name=supplier_name,
        excluded_normalized_skus=excluded_normalized_skus,
    )

    _notify_progress(progress_callback, 0.74, "Bygger export för utgående och nyheter")
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

    _notify_progress(progress_callback, 0.86, "Bygger export för prisuppdateringar")
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
        outgoing_excel_bytes=_df_excel_bytes(outgoing_export_df, sheet_name="Utg\u00e5ende"),
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
