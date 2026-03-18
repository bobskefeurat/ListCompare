"""Public comparison use cases and result models."""

from .use_cases import (
    ComparisonResults,
    SupplierArticleNumberReviewMatch,
    SupplierComparisonResults,
    build_comparison_results,
    build_supplier_comparison_results,
    filter_product_map_by_excluded_normalized_skus,
    filter_products_by_supplier_with_sku,
    unique_sorted_skus_from_mismatch_side,
    unique_sorted_skus_from_product_map,
)

__all__ = [
    "ComparisonResults",
    "SupplierArticleNumberReviewMatch",
    "SupplierComparisonResults",
    "build_comparison_results",
    "build_supplier_comparison_results",
    "filter_product_map_by_excluded_normalized_skus",
    "filter_products_by_supplier_with_sku",
    "unique_sorted_skus_from_mismatch_side",
    "unique_sorted_skus_from_product_map",
]
