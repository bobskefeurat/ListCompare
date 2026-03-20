"""Pure supplier compare orchestration behind the UI-facing wrappers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from ....core.comparison import SupplierComparisonResults, build_supplier_comparison_results
from ....core.products.product_mapping import build_product_map
from ....core.products.product_schema import HICORE_COLUMNS, Product
from ....core.suppliers.supplier_products import (
    build_supplier_map,
    find_supplier_id_column,
    find_supplier_price_column,
)
from ....core.suppliers.supplier_selection import normalized_skus_from_product_map
from ..compute_shared import _find_case_insensitive_column, _hicore_purchase_column_name
from ..io.brand_filter import _normalized_skus_for_excluded_brands
from ..io.uploads import _uploaded_csv_to_df


@dataclass(frozen=True)
class SupplierComputationArtifacts:
    supplier_df: pd.DataFrame
    comparison_results: SupplierComparisonResults
    id_column: str
    price_column: str
    purchase_column: Optional[str]
    brand_column: Optional[str]
    new_products_normalized_skus: set[str]
    out_of_stock_normalized_skus: set[str]
    out_of_stock_hicore_skus: dict[str, str]
    in_stock_normalized_skus: set[str]
    in_stock_hicore_skus: dict[str, str]
    warning_message: Optional[str]


def load_hicore_compare_df(hicore_bytes: bytes) -> pd.DataFrame:
    return _uploaded_csv_to_df(hicore_bytes, sep=";")


def _hicore_skus_by_normalized_sku(
    mismatch_map: dict[str, dict[str, list[Product]]],
) -> dict[str, str]:
    hicore_skus: dict[str, str] = {}
    for normalized_sku, sides in mismatch_map.items():
        for product in sides.get("hicore", []):
            sku = str(product.sku).strip()
            if sku != "":
                hicore_skus[normalized_sku] = sku
                break
    return hicore_skus


def build_supplier_artifacts(
    df_hicore: pd.DataFrame,
    *,
    supplier_name: str,
    supplier_df: pd.DataFrame,
    excluded_brands: Optional[list[str]] = None,
    profile_excluded_normalized_skus: Optional[set[str]] = None,
) -> SupplierComputationArtifacts:
    hicore_map = build_product_map(
        df_hicore,
        source="hicore",
        columns=HICORE_COLUMNS,
    )
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

    prepared_supplier_df = supplier_df.copy()
    supplier_source_columns = list(prepared_supplier_df.columns)
    id_column = find_supplier_id_column(prepared_supplier_df)
    price_column = find_supplier_price_column(prepared_supplier_df)
    purchase_column = _find_case_insensitive_column(
        supplier_source_columns,
        _hicore_purchase_column_name(),
    )
    brand_column = _find_case_insensitive_column(
        supplier_source_columns,
        HICORE_COLUMNS["brand"],
    )
    supplier_map = build_supplier_map(prepared_supplier_df)
    comparison_results = build_supplier_comparison_results(
        hicore_map,
        supplier_map,
        supplier_internal_name=supplier_name,
        excluded_normalized_skus=combined_excluded_normalized_skus,
    )
    return SupplierComputationArtifacts(
        supplier_df=prepared_supplier_df,
        comparison_results=comparison_results,
        id_column=id_column,
        price_column=price_column,
        purchase_column=purchase_column,
        brand_column=brand_column,
        new_products_normalized_skus=normalized_skus_from_product_map(comparison_results.new_products),
        out_of_stock_normalized_skus=set(comparison_results.price_updates_out_of_stock.keys()),
        out_of_stock_hicore_skus=_hicore_skus_by_normalized_sku(
            comparison_results.price_updates_out_of_stock
        ),
        in_stock_normalized_skus=set(comparison_results.price_updates_in_stock.keys()),
        in_stock_hicore_skus=_hicore_skus_by_normalized_sku(
            comparison_results.price_updates_in_stock
        ),
        warning_message=warning_message,
    )


def build_supplier_artifacts_from_uploads(
    hicore_bytes: bytes,
    *,
    supplier_name: str,
    supplier_df: pd.DataFrame,
    excluded_brands: Optional[list[str]] = None,
    profile_excluded_normalized_skus: Optional[set[str]] = None,
) -> SupplierComputationArtifacts:
    df_hicore = load_hicore_compare_df(hicore_bytes)
    return build_supplier_artifacts(
        df_hicore,
        supplier_name=supplier_name,
        supplier_df=supplier_df,
        excluded_brands=excluded_brands,
        profile_excluded_normalized_skus=profile_excluded_normalized_skus,
    )
