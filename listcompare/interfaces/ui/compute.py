from __future__ import annotations

from typing import Optional

from ...core.comparison_use_cases import (
    build_comparison_results,
    unique_sorted_skus_from_mismatch_side,
    unique_sorted_skus_from_product_map,
)
from ...core.product_model import HICORE_COLUMNS, build_product_map, prepare_data
from ...core.supplier_products import build_supplier_map
from .common import CompareUiResult, SupplierUiResult
from .data_io import (
    _mismatch_map_to_df,
    _normalized_skus_for_excluded_brands,
    _product_map_to_df,
    _read_supplier_upload,
    _sku_csv_bytes,
    _uploaded_csv_to_df,
)
def _compute_compare_result(
    hicore_bytes: bytes,
    magento_bytes: bytes,
    *,
    excluded_brands: Optional[list[str]] = None,
) -> CompareUiResult:
    df_hicore = _uploaded_csv_to_df(hicore_bytes, sep=";")
    df_magento = _uploaded_csv_to_df(magento_bytes, sep=";")
    hicore_map, magento_map = prepare_data(df_hicore, df_magento)
    excluded_normalized_skus, warning_message = _normalized_skus_for_excluded_brands(
        df_hicore,
        excluded_brands or [],
    )

    results = build_comparison_results(
        hicore_map,
        magento_map,
        excluded_normalized_skus=excluded_normalized_skus,
    )

    only_in_magento_skus = unique_sorted_skus_from_product_map(results.only_in_magento)
    stock_skus = unique_sorted_skus_from_mismatch_side(results.stock_mismatches, "magento")
    return CompareUiResult(
        only_in_magento_df=_product_map_to_df(results.only_in_magento),
        stock_mismatch_df=_mismatch_map_to_df(results.stock_mismatches),
        only_in_magento_csv_bytes=_sku_csv_bytes(only_in_magento_skus),
        stock_mismatch_csv_bytes=_sku_csv_bytes(stock_skus),
        only_in_magento_count=len(results.only_in_magento),
        stock_mismatch_count=len(results.stock_mismatches),
        warning_message=warning_message,
    )


def _compute_supplier_result(
    hicore_bytes: bytes,
    *,
    supplier_name: str,
    supplier_file_name: str,
    supplier_bytes: bytes,
    excluded_brands: Optional[list[str]] = None,
) -> SupplierUiResult:
    df_hicore = _uploaded_csv_to_df(hicore_bytes, sep=";")
    hicore_map = build_product_map(
        df_hicore,
        source="hicore",
        columns=HICORE_COLUMNS,
    )
    excluded_normalized_skus, warning_message = _normalized_skus_for_excluded_brands(
        df_hicore,
        excluded_brands or [],
    )
    df_supplier = _read_supplier_upload(supplier_file_name, supplier_bytes)
    supplier_map = build_supplier_map(df_supplier)
    results = build_comparison_results(
        hicore_map,
        {},
        supplier_map=supplier_map,
        supplier_internal_name=supplier_name,
        excluded_normalized_skus=excluded_normalized_skus,
    )

    internal_only_map = results.internal_only_candidates or {}
    internal_only_skus = unique_sorted_skus_from_product_map(internal_only_map)
    return SupplierUiResult(
        internal_only_df=_product_map_to_df(internal_only_map),
        internal_only_csv_bytes=_sku_csv_bytes(internal_only_skus),
        internal_only_count=len(internal_only_map),
        warning_message=warning_message,
    )



