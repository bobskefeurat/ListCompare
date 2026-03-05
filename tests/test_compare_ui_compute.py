import io
import unittest

import pandas as pd

from listcompare.core.product_model import HICORE_COLUMNS
from listcompare.interfaces.ui.compute import (
    _compute_compare_result,
    _compute_web_order_compare_result,
)


def _to_csv_bytes(df: pd.DataFrame, *, sep: str) -> bytes:
    return df.to_csv(sep=sep, index=False).encode("utf-8-sig")


def _read_csv_bytes(data: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(data), sep=";", dtype=str).fillna("")


class CompareUiComputeTests(unittest.TestCase):
    def test_compare_web_order_result_includes_magento_only_orders(self) -> None:
        sku_col = HICORE_COLUMNS["sku"]
        name_col = HICORE_COLUMNS["name"]
        total_col = HICORE_COLUMNS["total_stock"]
        reserved_col = HICORE_COLUMNS["reserved"]
        supplier_col = HICORE_COLUMNS["supplier"]

        df_hicore = pd.DataFrame(
            [
                {
                    sku_col: "001",
                    name_col: "Product A",
                    total_col: "4",
                    reserved_col: "1",
                    supplier_col: "EM Nordic",
                    "Webbordernr": "24539",
                },
                {
                    sku_col: "002",
                    name_col: "Product B",
                    total_col: "5",
                    reserved_col: "0",
                    supplier_col: "EM Nordic",
                    "Webbordernr": "000024541",
                },
            ]
        )
        df_magento = pd.DataFrame(
            [
                {
                    "sku": "1",
                    "name": "Product A",
                    "qty": "3",
                    "ID": "000024539",
                    "Status": "processing",
                },
                {
                    "sku": "003",
                    "name": "Product C",
                    "qty": "2",
                    "ID": "000024540",
                    "Status": "pending",
                },
            ]
        )

        result = _compute_web_order_compare_result(
            hicore_bytes=_to_csv_bytes(df_hicore, sep=";"),
            magento_bytes=_to_csv_bytes(df_magento, sep=","),
        )

        self.assertEqual(result.magento_only_web_orders_count, 1)
        self.assertEqual(result.warning_message, None)
        self.assertEqual(
            result.magento_only_web_orders_df["ID"].tolist(),
            ["000024540"],
        )
        self.assertEqual(
            result.magento_only_web_orders_df["Status"].tolist(),
            ["pending"],
        )

        export_df = _read_csv_bytes(result.magento_only_web_orders_csv_bytes)
        self.assertEqual(export_df.columns.tolist(), ["ID"])
        self.assertEqual(export_df["ID"].tolist(), ["000024540"])

    def test_compare_result_keeps_product_compare_when_order_columns_are_missing(self) -> None:
        sku_col = HICORE_COLUMNS["sku"]
        name_col = HICORE_COLUMNS["name"]
        total_col = HICORE_COLUMNS["total_stock"]
        reserved_col = HICORE_COLUMNS["reserved"]

        df_hicore = pd.DataFrame(
            [
                {
                    sku_col: "001",
                    name_col: "Product A",
                    total_col: "1",
                    reserved_col: "0",
                }
            ]
        )
        df_magento = pd.DataFrame(
            [
                {
                    "sku": "002",
                    "name": "Product B",
                    "qty": "2",
                }
            ]
        )

        result = _compute_compare_result(
            hicore_bytes=_to_csv_bytes(df_hicore, sep=";"),
            magento_bytes=_to_csv_bytes(df_magento, sep=";"),
        )

        self.assertEqual(result.only_in_magento_count, 1)
        self.assertEqual(result.stock_mismatch_count, 0)

    def test_compare_web_order_result_warns_when_order_columns_are_missing(self) -> None:
        df_hicore = pd.DataFrame([{"Ordernr": "10"}])
        df_magento = pd.DataFrame([{"Other": "20"}])

        result = _compute_web_order_compare_result(
            hicore_bytes=_to_csv_bytes(df_hicore, sep=";"),
            magento_bytes=_to_csv_bytes(df_magento, sep=","),
        )

        self.assertEqual(result.magento_only_web_orders_count, 0)
        self.assertEqual(
            result.warning_message,
            'HiCore-filen saknar kolumnen "Webbordernr".',
        )
        self.assertTrue(result.magento_only_web_orders_df.empty)


if __name__ == "__main__":
    unittest.main()
