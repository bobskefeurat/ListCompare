import io
import unittest

import pandas as pd
from openpyxl import Workbook, load_workbook

from listcompare.core.products.product_mapping import build_product_map
from listcompare.core.products.product_schema import HICORE_COLUMNS
from listcompare.core.suppliers.profile import build_supplier_hicore_renamed_copy
from listcompare.interfaces.ui.io.exports import _df_excel_bytes
from listcompare.interfaces.ui.io.uploads import _read_supplier_upload
from listcompare.interfaces.ui.services.compare_pipeline import load_hicore_compare_df


def _xlsx_bytes_from_rows(rows: list[list[object]], *, number_formats: dict[str, str]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    for row in rows:
        worksheet.append(row)

    for cell_ref, number_format in number_formats.items():
        worksheet[cell_ref].number_format = number_format

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _hicore_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(sep=";", index=False).encode("utf-8-sig")


class UiUploadTests(unittest.TestCase):
    def test_read_supplier_upload_preserves_zero_padded_numeric_excel_cells(self) -> None:
        upload_bytes = _xlsx_bytes_from_rows(
            [
                ["SupplierSku", "SupplierArticleNo", "Price"],
                [123, 45, 99.95],
            ],
            number_formats={
                "A2": "000000",
                "B2": "0000",
                "C2": "0.00",
            },
        )

        df_supplier = _read_supplier_upload("supplier.xlsx", upload_bytes)

        self.assertEqual(df_supplier["SupplierSku"].tolist(), ["000123"])
        self.assertEqual(df_supplier["SupplierArticleNo"].tolist(), ["0045"])
        self.assertEqual(df_supplier["Price"].tolist(), ["99.95"])

    def test_supplier_transform_checkbox_respects_zero_padded_excel_upload_values(self) -> None:
        upload_bytes = _xlsx_bytes_from_rows(
            [
                ["SupplierSku", "NameCol"],
                [123, "Product A"],
            ],
            number_formats={"A2": "000000"},
        )
        df_supplier = _read_supplier_upload("supplier.xlsx", upload_bytes)

        renamed_keep = build_supplier_hicore_renamed_copy(
            df_supplier,
            target_to_source={
                "Art.märkning": "SupplierSku",
                "Artikelnamn": "NameCol",
            },
            supplier_name="EM Nordic",
            strip_leading_zeros_from_sku=False,
        )
        renamed_strip = build_supplier_hicore_renamed_copy(
            df_supplier,
            target_to_source={
                "Art.märkning": "SupplierSku",
                "Artikelnamn": "NameCol",
            },
            supplier_name="EM Nordic",
            strip_leading_zeros_from_sku=True,
        )

        self.assertEqual(renamed_keep["Art.märkning"].tolist(), ["000123"])
        self.assertEqual(renamed_strip["Art.märkning"].tolist(), ["123"])

        workbook = load_workbook(
            io.BytesIO(_df_excel_bytes(renamed_keep, sheet_name="HiCore-format")),
            data_only=False,
        )
        sheet = workbook.active
        self.assertEqual(sheet["A1"].value, "Art.märkning")
        self.assertEqual(sheet["A2"].value, "000123")
        self.assertEqual(sheet["A2"].number_format, "@")

    def test_hicore_csv_load_and_product_map_preserve_leading_zeroes(self) -> None:
        sku_col = HICORE_COLUMNS["sku"]
        name_col = HICORE_COLUMNS["name"]
        stock_col = HICORE_COLUMNS["stock"]
        price_col = HICORE_COLUMNS["price"]
        supplier_col = HICORE_COLUMNS["supplier"]
        df_hicore = pd.DataFrame(
            [
                {
                    sku_col: "000123",
                    name_col: "Product A",
                    stock_col: "1",
                    price_col: "10",
                    supplier_col: "EM Nordic",
                }
            ]
        )

        loaded_df = load_hicore_compare_df(_hicore_csv_bytes(df_hicore))
        hicore_map = build_product_map(
            loaded_df,
            source="hicore",
            columns=HICORE_COLUMNS,
        )

        self.assertEqual(loaded_df[sku_col].tolist(), ["000123"])
        self.assertEqual(list(hicore_map.keys()), ["000123"])
        self.assertEqual(hicore_map["000123"][0].sku, "000123")


if __name__ == "__main__":
    unittest.main()
