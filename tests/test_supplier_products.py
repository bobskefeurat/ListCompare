import unittest

import pandas as pd

from listcompare.core.supplier_products import build_supplier_map, find_supplier_id_column


class SupplierProductsTests(unittest.TestCase):
    def test_find_supplier_id_column_accepts_art_markning(self) -> None:
        df_supplier = pd.DataFrame(
            {
                "Art.m\u00e4rkning": ["1001", "1002"],
                "Name": ["A", "B"],
            }
        )

        id_col = find_supplier_id_column(df_supplier)

        self.assertEqual(id_col, "Art.m\u00e4rkning")

    def test_find_supplier_id_column_prioritizes_ean_when_available(self) -> None:
        df_supplier = pd.DataFrame(
            {
                "UPC": ["222"],
                "EAN": ["111"],
                "Art.m\u00e4rkning": ["333"],
            }
        )

        id_col = find_supplier_id_column(df_supplier)

        self.assertEqual(id_col, "EAN")

    def test_build_supplier_map_uses_art_markning_and_skips_empty_values(self) -> None:
        df_supplier = pd.DataFrame(
            {
                "Art.m\u00e4rkning": ["A1", "", None, "A2", " nan "],
            }
        )

        supplier_map = build_supplier_map(df_supplier)

        self.assertEqual(set(supplier_map.keys()), {"A1", "A2"})
        self.assertEqual(supplier_map["A1"][0].source, "supplier")
        self.assertEqual(supplier_map["A1"][0].sku, "A1")


if __name__ == "__main__":
    unittest.main()
