import unittest

from listcompare.core.comparison_use_cases import (
    build_comparison_results,
    filter_product_map_by_excluded_normalized_skus,
    filter_products_by_supplier_with_sku,
    unique_sorted_skus_from_mismatch_side,
    unique_sorted_skus_from_product_map,
)
from listcompare.core.product_model import Product


def make_product(
    *,
    sku: str,
    source: str,
    supplier: str = "",
    name: str = "",
    stock: str = "",
) -> Product:
    return Product(sku=sku, name=name, stock=stock, supplier=supplier, source=source)


class ComparisonUseCaseTests(unittest.TestCase):
    def test_filter_products_by_supplier_with_sku_removes_empty_skus(self) -> None:
        hicore_map = {
            "111": [make_product(sku="111", source="hicore", supplier="EM Nordic")],
            "222": [make_product(sku="222", source="hicore", supplier="Other Supplier")],
            "": [make_product(sku="", source="hicore", supplier="EM Nordic")],
        }

        filtered = filter_products_by_supplier_with_sku(hicore_map, "EM Nordic")

        self.assertEqual(set(filtered.keys()), {"111"})

    def test_build_comparison_results_creates_internal_only_candidates(self) -> None:
        hicore_map = {
            "111": [make_product(sku="111", source="hicore", supplier="EM Nordic")],
            "333": [make_product(sku="333", source="hicore", supplier="EM Nordic")],
            "444": [make_product(sku="444", source="hicore", supplier="Other")],
        }
        magento_map = {
            "111": [make_product(sku="111", source="magento", stock="5")],
        }
        supplier_map = {
            "111": [make_product(sku="111", source="supplier")],
        }

        results = build_comparison_results(
            hicore_map,
            magento_map,
            supplier_map=supplier_map,
            supplier_internal_name="EM Nordic",
        )

        self.assertIsNotNone(results.internal_only_candidates)
        assert results.internal_only_candidates is not None
        self.assertEqual(set(results.internal_only_candidates.keys()), {"333"})

    def test_filter_product_map_by_excluded_normalized_skus(self) -> None:
        product_map = {
            "00123": [make_product(sku="00123", source="hicore")],
            "77": [make_product(sku="77", source="hicore")],
        }

        filtered = filter_product_map_by_excluded_normalized_skus(product_map, {"123"})

        self.assertEqual(set(filtered.keys()), {"77"})

    def test_build_comparison_results_excludes_normalized_skus_from_all_outputs(self) -> None:
        hicore_map = {
            "001": [make_product(sku="001", source="hicore", supplier="EM Nordic", stock="5")],
            "003": [make_product(sku="003", source="hicore", supplier="EM Nordic", stock="2")],
        }
        magento_map = {
            "1": [make_product(sku="1", source="magento", stock="9")],
            "004": [make_product(sku="004", source="magento", stock="1")],
        }
        supplier_map = {
            "003": [make_product(sku="003", source="supplier")],
        }

        results = build_comparison_results(
            hicore_map,
            magento_map,
            supplier_map=supplier_map,
            supplier_internal_name="EM Nordic",
            excluded_normalized_skus={"1"},
        )

        self.assertEqual(set(results.only_in_magento.keys()), {"004"})
        self.assertEqual(results.stock_mismatches, {})
        assert results.internal_only_candidates is not None
        self.assertEqual(results.internal_only_candidates, {})

    def test_unique_sorted_sku_helpers(self) -> None:
        sku_map = {
            "a": [make_product(sku="002", source="hicore"), make_product(sku="001", source="hicore")],
            "b": [make_product(sku="", source="hicore")],
        }
        mismatch_map = {
            "2": {
                "hicore": [make_product(sku="002", source="hicore")],
                "magento": [make_product(sku="02", source="magento"), make_product(sku="02", source="magento")],
            }
        }

        self.assertEqual(unique_sorted_skus_from_product_map(sku_map), ["001", "002"])
        self.assertEqual(unique_sorted_skus_from_mismatch_side(mismatch_map, "magento"), ["02"])


if __name__ == "__main__":
    unittest.main()
