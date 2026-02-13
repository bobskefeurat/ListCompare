import unittest

from listcompare.core.product_diff import find_field_mismatches_by_sku, find_missing_skus, normalize_sku
from listcompare.core.product_model import Product


def make_product(
    *,
    sku: str,
    source: str,
    name: str = "",
    stock: str = "",
    supplier: str = "",
) -> Product:
    return Product(sku=sku, name=name, stock=stock, supplier=supplier, source=source)


class ProductDiffTests(unittest.TestCase):
    def test_normalize_sku_strips_leading_zeroes(self) -> None:
        self.assertEqual(normalize_sku("00042"), "42")
        self.assertEqual(normalize_sku("0"), "0")
        self.assertEqual(normalize_sku(""), "")

    def test_find_missing_skus_uses_normalized_keys(self) -> None:
        hicore_map = {
            "00123": [make_product(sku="00123", source="hicore", stock="5")],
        }
        magento_map = {
            "123": [make_product(sku="123", source="magento", stock="5")],
            "00999": [make_product(sku="00999", source="magento", stock="2")],
        }

        only_in_hicore, only_in_magento = find_missing_skus(hicore_map, magento_map)

        self.assertEqual(only_in_hicore, {})
        self.assertEqual(set(only_in_magento.keys()), {"00999"})

    def test_find_field_mismatches_by_sku_detects_stock_difference(self) -> None:
        hicore_map = {
            "0001": [make_product(sku="0001", source="hicore", name="Amp", stock="10")],
        }
        magento_map = {
            "1": [make_product(sku="1", source="magento", name="Amp", stock="8")],
        }

        mismatches = find_field_mismatches_by_sku(hicore_map, magento_map, field="stock")

        self.assertEqual(set(mismatches.keys()), {"1"})
        self.assertEqual(mismatches["1"]["hicore"][0].stock, "10")
        self.assertEqual(mismatches["1"]["magento"][0].stock, "8")


if __name__ == "__main__":
    unittest.main()
