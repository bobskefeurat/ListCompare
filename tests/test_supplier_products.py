import unittest

import pandas as pd

from listcompare.core.suppliers.supplier_products import (
    build_supplier_map,
    find_supplier_id_column,
    find_supplier_name_column,
    find_supplier_price_column,
)


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
                "UtprisInklMoms": ["10", "20", "30", "40,00 SEK", "50"],
            }
        )

        supplier_map = build_supplier_map(df_supplier)

        self.assertEqual(set(supplier_map.keys()), {"A1", "A2"})
        self.assertEqual(supplier_map["A1"][0].source, "supplier")
        self.assertEqual(supplier_map["A1"][0].sku, "A1")
        self.assertEqual(supplier_map["A1"][0].price, "10")
        self.assertEqual(supplier_map["A2"][0].price, "40")

    def test_find_supplier_price_column_accepts_utpris(self) -> None:
        df_supplier = pd.DataFrame(
            {
                "Art.m\u00e4rkning": ["A1"],
                "UtprisInklMoms": ["10"],
            }
        )

        price_col = find_supplier_price_column(df_supplier)

        self.assertEqual(price_col, "UtprisInklMoms")

    def test_build_supplier_map_reads_name_when_available(self) -> None:
        df_supplier = pd.DataFrame(
            {
                "Art.m\u00e4rkning": ["A1"],
                "Artikelnamn": ["Produkt A"],
                "UtprisInklMoms": ["10"],
            }
        )

        supplier_map = build_supplier_map(df_supplier)

        self.assertEqual(supplier_map["A1"][0].name, "Produkt A")

    def test_find_supplier_name_column_returns_none_when_missing(self) -> None:
        df_supplier = pd.DataFrame(
            {
                "Art.m\u00e4rkning": ["A1"],
                "UtprisInklMoms": ["10"],
            }
        )

        name_col = find_supplier_name_column(df_supplier)

        self.assertIsNone(name_col)


if __name__ == "__main__":
    unittest.main()
