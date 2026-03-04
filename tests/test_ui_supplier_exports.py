import io
import unittest

import pandas as pd

from listcompare.core.product_model import HICORE_COLUMNS
from listcompare.interfaces.supplier_profile_utils import (
    SUPPLIER_HICORE_RENAME_COLUMNS,
    SUPPLIER_HICORE_SUPPLIER_COLUMN,
)
from listcompare.interfaces.ui.compute import _compute_supplier_result


def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(sep=";", index=False).encode("utf-8-sig")


def _read_excel_bytes(data: bytes) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(data), dtype=str).fillna("")


def _purchase_column_name() -> str:
    for column_name in SUPPLIER_HICORE_RENAME_COLUMNS:
        cleaned = str(column_name).strip()
        if cleaned.casefold() == "ink\u00f6pspris".casefold():
            return cleaned
    return "Ink\u00f6pspris"


class SupplierUiExportTests(unittest.TestCase):
    def test_supplier_exports_use_expected_columns_per_category(self) -> None:
        sku_col = HICORE_COLUMNS["sku"]
        name_col = HICORE_COLUMNS["name"]
        supplier_col = HICORE_COLUMNS["supplier"]
        total_col = HICORE_COLUMNS["total_stock"]
        reserved_col = HICORE_COLUMNS["reserved"]
        price_col = HICORE_COLUMNS["price"]
        purchase_col = _purchase_column_name()

        df_hicore = pd.DataFrame(
            [
                {
                    sku_col: "100",
                    name_col: "SKU 100",
                    total_col: "0",
                    reserved_col: "0",
                    price_col: "10",
                    supplier_col: "EM Nordic",
                },
                {
                    sku_col: "200",
                    name_col: "SKU 200",
                    total_col: "3",
                    reserved_col: "0",
                    price_col: "20",
                    supplier_col: "EM Nordic",
                },
                {
                    sku_col: "300",
                    name_col: "SKU 300",
                    total_col: "2",
                    reserved_col: "0",
                    price_col: "30",
                    supplier_col: "EM Nordic",
                },
            ]
        )
        hicore_bytes = _to_csv_bytes(df_hicore)

        supplier_columns = [*SUPPLIER_HICORE_RENAME_COLUMNS, SUPPLIER_HICORE_SUPPLIER_COLUMN]
        base_row = {column: "" for column in supplier_columns}
        df_supplier = pd.DataFrame(
            [
                {
                    **base_row,
                    sku_col: "100",
                    name_col: "SKU 100 supplier",
                    purchase_col: "5",
                    price_col: "11",
                    SUPPLIER_HICORE_SUPPLIER_COLUMN: "EM Nordic",
                },
                {
                    **base_row,
                    sku_col: "200",
                    name_col: "SKU 200 supplier",
                    purchase_col: "8",
                    price_col: "21",
                    SUPPLIER_HICORE_SUPPLIER_COLUMN: "EM Nordic",
                },
                {
                    **base_row,
                    sku_col: "400",
                    name_col: "SKU 400 supplier",
                    purchase_col: "12",
                    price_col: "40",
                    SUPPLIER_HICORE_SUPPLIER_COLUMN: "EM Nordic",
                },
            ]
        )
        supplier_bytes = _to_csv_bytes(df_supplier)

        result = _compute_supplier_result(
            hicore_bytes=hicore_bytes,
            supplier_name="EM Nordic",
            supplier_file_name="supplier.csv",
            supplier_bytes=supplier_bytes,
        )

        outgoing_export = _read_excel_bytes(result.outgoing_excel_bytes)
        self.assertEqual(outgoing_export.columns.tolist(), [sku_col])
        self.assertEqual(outgoing_export[sku_col].tolist(), ["300"])

        new_products_export = _read_excel_bytes(result.new_products_excel_bytes)
        self.assertEqual(new_products_export.columns.tolist(), supplier_columns)
        self.assertEqual(new_products_export[sku_col].tolist(), ["400"])

        out_of_stock_export = _read_excel_bytes(result.price_updates_out_of_stock_excel_bytes)
        self.assertEqual(out_of_stock_export.columns.tolist(), [sku_col, purchase_col, price_col])
        self.assertEqual(out_of_stock_export[sku_col].tolist(), ["100"])
        self.assertEqual(out_of_stock_export[purchase_col].tolist(), ["5"])
        self.assertEqual(out_of_stock_export[price_col].tolist(), ["11"])

        in_stock_export = _read_excel_bytes(result.price_updates_in_stock_excel_bytes)
        self.assertEqual(in_stock_export.columns.tolist(), [sku_col, price_col])
        self.assertEqual(in_stock_export[sku_col].tolist(), ["200"])
        self.assertEqual(in_stock_export[price_col].tolist(), ["21"])


if __name__ == "__main__":
    unittest.main()
