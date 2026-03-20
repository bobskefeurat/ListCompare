import unittest

import pandas as pd

from listcompare.core.products.product_schema import HICORE_COLUMNS
from listcompare.interfaces.ui.services.supplier_pipeline import (
    build_supplier_artifacts,
    load_hicore_compare_df,
)


def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(sep=";", index=False).encode("utf-8-sig")


class SupplierPipelineTests(unittest.TestCase):
    def test_load_hicore_compare_df_reads_semicolon_upload(self) -> None:
        df_hicore = pd.DataFrame([{HICORE_COLUMNS["sku"]: "001"}])

        loaded_df = load_hicore_compare_df(_to_csv_bytes(df_hicore))

        self.assertEqual(loaded_df[HICORE_COLUMNS["sku"]].tolist(), ["001"])

    def test_build_supplier_artifacts_collects_domain_results_and_columns(self) -> None:
        sku_col = HICORE_COLUMNS["sku"]
        name_col = HICORE_COLUMNS["name"]
        brand_col = HICORE_COLUMNS["brand"]
        supplier_col = HICORE_COLUMNS["supplier"]
        total_col = HICORE_COLUMNS["total_stock"]
        reserved_col = HICORE_COLUMNS["reserved"]
        price_col = HICORE_COLUMNS["price"]
        purchase_col = "Inköpspris"

        df_hicore = pd.DataFrame(
            [
                {
                    sku_col: "00100",
                    name_col: "SKU 100",
                    total_col: "0",
                    reserved_col: "0",
                    price_col: "10",
                    supplier_col: "EM Nordic",
                },
                {
                    sku_col: "00200",
                    name_col: "SKU 200",
                    total_col: "3",
                    reserved_col: "0",
                    price_col: "20",
                    supplier_col: "EM Nordic",
                },
                {
                    sku_col: "00300",
                    name_col: "SKU 300",
                    total_col: "2",
                    reserved_col: "0",
                    price_col: "30",
                    supplier_col: "EM Nordic",
                },
            ]
        )
        df_supplier = pd.DataFrame(
            [
                {
                    sku_col: "100",
                    name_col: "SKU 100 supplier",
                    brand_col: "Brand 100",
                    purchase_col: "5",
                    price_col: "11",
                    supplier_col: "EM Nordic",
                },
                {
                    sku_col: "200",
                    name_col: "SKU 200 supplier",
                    brand_col: "Brand 200",
                    purchase_col: "8",
                    price_col: "21",
                    supplier_col: "EM Nordic",
                },
                {
                    sku_col: "400",
                    name_col: "SKU 400 supplier",
                    brand_col: "Brand 400",
                    purchase_col: "12",
                    price_col: "40",
                    supplier_col: "EM Nordic",
                },
            ]
        )

        artifacts = build_supplier_artifacts(
            df_hicore,
            supplier_name="EM Nordic",
            supplier_df=df_supplier,
        )

        self.assertEqual(artifacts.id_column, sku_col)
        self.assertEqual(artifacts.price_column, price_col)
        self.assertEqual(artifacts.purchase_column, purchase_col)
        self.assertEqual(artifacts.brand_column, brand_col)
        self.assertEqual(len(artifacts.comparison_results.outgoing), 1)
        self.assertEqual(len(artifacts.comparison_results.new_products), 1)
        self.assertEqual(len(artifacts.out_of_stock_normalized_skus), 1)
        self.assertEqual(len(artifacts.in_stock_normalized_skus), 1)
        self.assertEqual(artifacts.warning_message, None)


if __name__ == "__main__":
    unittest.main()
