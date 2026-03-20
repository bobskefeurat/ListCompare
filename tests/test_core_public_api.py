import unittest

from listcompare.core.comparison import (
    build_comparison_results,
    build_supplier_comparison_results,
    filter_product_map_by_excluded_normalized_skus,
    filter_products_by_supplier_with_sku,
    unique_sorted_skus_from_mismatch_side,
    unique_sorted_skus_from_product_map,
)
from listcompare.core.comparison.use_cases import (
    build_comparison_results as build_comparison_results_impl,
)
from listcompare.core.comparison.use_cases import (
    build_supplier_comparison_results as build_supplier_comparison_results_impl,
)
from listcompare.core.comparison.use_cases import (
    filter_product_map_by_excluded_normalized_skus as filter_product_map_by_excluded_normalized_skus_impl,
)
from listcompare.core.comparison.use_cases import (
    filter_products_by_supplier_with_sku as filter_products_by_supplier_with_sku_impl,
)
from listcompare.core.comparison.use_cases import (
    unique_sorted_skus_from_mismatch_side as unique_sorted_skus_from_mismatch_side_impl,
)
from listcompare.core.comparison.use_cases import (
    unique_sorted_skus_from_product_map as unique_sorted_skus_from_product_map_impl,
)
from listcompare.core.products import (
    repair_magento_shift_rows_v1,
    repair_shifted_magento_rows,
)
from listcompare.core.products.repair_magento_export import (
    repair_magento_shift_rows_v1 as repair_magento_shift_rows_v1_impl,
)
from listcompare.core.products.repair_magento_export import (
    repair_shifted_magento_rows as repair_shifted_magento_rows_impl,
)


class CorePublicApiTests(unittest.TestCase):
    def test_comparison_package_reexports_use_case_api(self) -> None:
        self.assertIs(build_comparison_results, build_comparison_results_impl)
        self.assertIs(
            build_supplier_comparison_results,
            build_supplier_comparison_results_impl,
        )
        self.assertIs(
            filter_product_map_by_excluded_normalized_skus,
            filter_product_map_by_excluded_normalized_skus_impl,
        )
        self.assertIs(
            filter_products_by_supplier_with_sku,
            filter_products_by_supplier_with_sku_impl,
        )
        self.assertIs(
            unique_sorted_skus_from_mismatch_side,
            unique_sorted_skus_from_mismatch_side_impl,
        )
        self.assertIs(
            unique_sorted_skus_from_product_map,
            unique_sorted_skus_from_product_map_impl,
        )

    def test_products_package_reexports_single_magento_repair_source(self) -> None:
        self.assertIs(repair_shifted_magento_rows, repair_shifted_magento_rows_impl)
        self.assertIs(
            repair_magento_shift_rows_v1,
            repair_magento_shift_rows_v1_impl,
        )


if __name__ == "__main__":
    unittest.main()
