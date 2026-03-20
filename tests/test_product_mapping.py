import unittest

import pandas as pd

from listcompare.core.products.product_mapping import build_product_map
from listcompare.core.products.product_schema import HICORE_COLUMNS


class ProductMappingTests(unittest.TestCase):
    def test_build_product_map_uses_computed_hicore_stock_when_available(self) -> None:
        df_hicore = pd.DataFrame(
            [
                {
                    HICORE_COLUMNS["sku"]: "100",
                    HICORE_COLUMNS["name"]: "Receiver",
                    HICORE_COLUMNS["stock"]: "99",
                    HICORE_COLUMNS["total_stock"]: "5",
                    HICORE_COLUMNS["reserved"]: "2",
                }
            ]
        )

        hicore_map = build_product_map(
            df_hicore,
            source="hicore",
            columns=HICORE_COLUMNS,
        )

        self.assertEqual(hicore_map["100"][0].stock, "3")

    def test_build_product_map_falls_back_to_direct_hicore_stock_when_computed_columns_are_missing(
        self,
    ) -> None:
        df_hicore = pd.DataFrame(
            [
                {
                    HICORE_COLUMNS["sku"]: "100",
                    HICORE_COLUMNS["name"]: "Receiver",
                    HICORE_COLUMNS["stock"]: "7",
                }
            ]
        )

        hicore_map = build_product_map(
            df_hicore,
            source="hicore",
            columns=HICORE_COLUMNS,
        )

        self.assertEqual(hicore_map["100"][0].stock, "7")

    def test_build_product_map_falls_back_to_direct_hicore_stock_when_total_is_unusable(self) -> None:
        df_hicore = pd.DataFrame(
            [
                {
                    HICORE_COLUMNS["sku"]: "100",
                    HICORE_COLUMNS["name"]: "Receiver",
                    HICORE_COLUMNS["stock"]: "4",
                    HICORE_COLUMNS["reserved"]: "1",
                }
            ]
        )

        hicore_map = build_product_map(
            df_hicore,
            source="hicore",
            columns=HICORE_COLUMNS,
        )

        self.assertEqual(hicore_map["100"][0].stock, "4")


if __name__ == "__main__":
    unittest.main()
