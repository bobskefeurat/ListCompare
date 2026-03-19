"""UI service helpers for supplier compare previews and export files."""

from __future__ import annotations

from typing import Optional

import pandas as pd

from ....core.comparison.use_cases import (
    build_supplier_comparison_results,
    unique_sorted_skus_from_product_map,
)
from ....core.products.product_diff import normalize_sku
from ....core.products.product_mapping import build_product_map
from ....core.products.product_schema import HICORE_COLUMNS, Product
from ....core.suppliers.supplier_products import (
    build_supplier_map,
    find_supplier_id_column,
    find_supplier_price_column,
)
from ....core.suppliers.supplier_selection import (
    filter_rows_by_normalized_skus,
    normalized_skus_from_product_map,
)
from ..common import SupplierUiResult
from ..compute_shared import (
    ProgressCallback,
    _find_case_insensitive_column,
    _hicore_purchase_column_name,
    _notify_progress,
    _sort_df_by_sku_column,
    _to_clean_text,
)
from ..io.brand_filter import _normalized_skus_for_excluded_brands
from ..io.exports import _df_excel_bytes
from ..io.tables import (
    _article_number_review_matches_to_df,
    _mismatch_map_to_df,
    _product_map_to_df,
)
from ..io.uploads import _uploaded_csv_to_df


def _build_supplier_price_export_df(
    df_supplier: pd.DataFrame,
    *,
    id_column: str,
    price_column: str,
    purchase_column: Optional[str],
    brand_column: Optional[str],
    normalized_skus: set[str],
    hicore_skus_by_normalized_sku: Optional[dict[str, str]] = None,
) -> pd.DataFrame:
    """Build a supplier price export and prefer the HiCore SKU representation."""

    sku_column_name = HICORE_COLUMNS["sku"]
    price_column_name = HICORE_COLUMNS["price"]
    purchase_column_name = _hicore_purchase_column_name()
    brand_column_name = HICORE_COLUMNS["brand"]
    export_columns = [sku_column_name, purchase_column_name, price_column_name, brand_column_name]

    filtered_rows = filter_rows_by_normalized_skus(
        df_supplier,
        sku_column=id_column,
        normalized_skus=normalized_skus,
    )
    if filtered_rows.empty:
        return pd.DataFrame(columns=export_columns)

    cleaned_skus = filtered_rows[id_column].map(_to_clean_text)
    normalized_row_skus = cleaned_skus.map(lambda value: normalize_sku(str(value)))
    export_df = pd.DataFrame()
    export_df[sku_column_name] = [
        hicore_skus_by_normalized_sku.get(normalized_sku, raw_sku)
        if hicore_skus_by_normalized_sku is not None
        else raw_sku
        for raw_sku, normalized_sku in zip(cleaned_skus.tolist(), normalized_row_skus.tolist())
    ]
    if purchase_column is not None and purchase_column in filtered_rows.columns:
        export_df[purchase_column_name] = filtered_rows[purchase_column].map(_to_clean_text).tolist()
    else:
        export_df[purchase_column_name] = ""
    export_df[price_column_name] = filtered_rows[price_column].map(_to_clean_text).tolist()
    if brand_column is not None and brand_column in filtered_rows.columns:
        export_df[brand_column_name] = filtered_rows[brand_column].map(_to_clean_text).tolist()
    else:
        export_df[brand_column_name] = ""
    return _sort_df_by_sku_column(export_df, sku_column=sku_column_name)


def _build_article_number_review_export_df(article_number_review_df: pd.DataFrame) -> pd.DataFrame:
    """Export only supplier-side rows that need SKU/article-number follow-up."""

    supplier_rows = article_number_review_df
    if "source" in supplier_rows.columns:
        supplier_rows = supplier_rows[
            supplier_rows["source"].map(lambda value: str(value).strip().casefold() == "supplier")
        ]

    export_df = pd.DataFrame()
    export_df[HICORE_COLUMNS["sku"]] = (
        supplier_rows["sku"].map(_to_clean_text).tolist() if "sku" in supplier_rows.columns else []
    )
    export_df[HICORE_COLUMNS["article_number"]] = (
        supplier_rows["article_number"].map(_to_clean_text).tolist()
        if "article_number" in supplier_rows.columns
        else []
    )
    export_df[HICORE_COLUMNS["name"]] = (
        supplier_rows["name"].map(_to_clean_text).tolist() if "name" in supplier_rows.columns else []
    )
    return export_df.reset_index(drop=True)


def _hicore_skus_by_normalized_sku(
    mismatch_map: dict[str, dict[str, list[Product]]],
) -> dict[str, str]:
    """Map each normalized mismatch SKU to the first non-empty HiCore SKU value."""

    hicore_skus: dict[str, str] = {}
    for normalized_sku, sides in mismatch_map.items():
        for product in sides.get("hicore", []):
            sku = str(product.sku).strip()
            if sku != "":
                hicore_skus[normalized_sku] = sku
                break
    return hicore_skus


def compute_supplier_result(
    hicore_bytes: bytes,
    *,
    supplier_name: str,
    supplier_df: pd.DataFrame,
    excluded_brands: Optional[list[str]] = None,
    profile_excluded_normalized_skus: Optional[set[str]] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> SupplierUiResult:
    """Compute supplier compare previews and export payloads for the UI."""

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
    combined_excluded_normalized_skus = {
        sku
        for sku in (profile_excluded_normalized_skus or set())
        if str(sku).strip() != ""
    }
    combined_excluded_normalized_skus.update(excluded_normalized_skus)
    _notify_progress(progress_callback, 0.35, "Förbereder leverantörsdata")
    df_supplier = supplier_df.copy()
    supplier_source_columns = list(df_supplier.columns)
    id_column = find_supplier_id_column(df_supplier)
    price_column = find_supplier_price_column(df_supplier)
    purchase_column = _find_case_insensitive_column(
        supplier_source_columns,
        _hicore_purchase_column_name(),
    )
    brand_column = _find_case_insensitive_column(
        supplier_source_columns,
        HICORE_COLUMNS["brand"],
    )
    _notify_progress(progress_callback, 0.50, "Bygger leverantörskarta")
    supplier_map = build_supplier_map(df_supplier)
    _notify_progress(progress_callback, 0.62, "Jämför mot HiCore")
    results = build_supplier_comparison_results(
        hicore_map,
        supplier_map,
        supplier_internal_name=supplier_name,
        excluded_normalized_skus=combined_excluded_normalized_skus,
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

    new_products_normalized_skus = normalized_skus_from_product_map(results.new_products)
    new_products_export_df = _sort_df_by_sku_column(
        filter_rows_by_normalized_skus(
            df_supplier,
            sku_column=id_column,
            normalized_skus=new_products_normalized_skus,
        ),
        sku_column=id_column,
    )

    _notify_progress(progress_callback, 0.86, "Bygger export för prisuppdateringar")
    out_of_stock_normalized_skus = set(results.price_updates_out_of_stock.keys())
    in_stock_normalized_skus = set(results.price_updates_in_stock.keys())
    out_of_stock_hicore_skus = _hicore_skus_by_normalized_sku(results.price_updates_out_of_stock)
    in_stock_hicore_skus = _hicore_skus_by_normalized_sku(results.price_updates_in_stock)
    price_updates_out_of_stock_export_df = _build_supplier_price_export_df(
        df_supplier,
        id_column=id_column,
        price_column=price_column,
        purchase_column=purchase_column,
        brand_column=brand_column,
        normalized_skus=out_of_stock_normalized_skus,
        hicore_skus_by_normalized_sku=out_of_stock_hicore_skus,
    )
    price_updates_in_stock_export_df = _build_supplier_price_export_df(
        df_supplier,
        id_column=id_column,
        price_column=price_column,
        purchase_column=purchase_column,
        brand_column=brand_column,
        normalized_skus=in_stock_normalized_skus,
        hicore_skus_by_normalized_sku=in_stock_hicore_skus,
    )
    article_number_review_df = _article_number_review_matches_to_df(
        results.article_number_review_matches
    )
    article_number_review_export_df = _build_article_number_review_export_df(
        article_number_review_df
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
        article_number_review_df=article_number_review_df,
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
        article_number_review_excel_bytes=_df_excel_bytes(
            article_number_review_export_df,
            sheet_name="SKU-Artikelnummer-diff",
        ),
        outgoing_count=len(results.outgoing),
        new_products_count=len(results.new_products),
        price_updates_out_of_stock_count=len(results.price_updates_out_of_stock),
        price_updates_in_stock_count=len(results.price_updates_in_stock),
        article_number_review_count=len(results.article_number_review_matches),
        warning_message=warning_message,
    )
    _notify_progress(progress_callback, 1.0, "Klar")
    return result
