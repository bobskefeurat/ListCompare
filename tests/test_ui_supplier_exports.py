import io
import unittest

import pandas as pd
from openpyxl import load_workbook

from listcompare.core.products.product_schema import HICORE_COLUMNS
from listcompare.core.suppliers.prepare import (
    build_supplier_prepare_analysis,
    finalize_supplier_prepare_analysis,
)
from listcompare.core.suppliers.profile import (
    SUPPLIER_HICORE_RENAME_COLUMNS,
    SUPPLIER_HICORE_SUPPLIER_COLUMN,
)
from listcompare.interfaces.ui.features.supplier_compare.results import (
    _supplier_compare_export_file_name,
)
from listcompare.interfaces.ui.services.supplier_compute import compute_supplier_result


def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(sep=";", index=False).encode("utf-8-sig")


def _read_excel_bytes(data: bytes) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(data), dtype=str).fillna("")


def _load_excel_workbook(data: bytes):
    return load_workbook(io.BytesIO(data), data_only=False)


def _purchase_column_name() -> str:
    for column_name in SUPPLIER_HICORE_RENAME_COLUMNS:
        cleaned = str(column_name).strip()
        if cleaned.casefold() == "ink\u00f6pspris".casefold():
            return cleaned
    return "Ink\u00f6pspris"


class SupplierUiExportTests(unittest.TestCase):
    def test_supplier_compare_export_file_name_includes_supplier_name(self) -> None:
        self.assertEqual(
            _supplier_compare_export_file_name(
                supplier_name="EM Nordic",
                label="Prisuppdatering, Ej i lager",
            ),
            "EM_Nordic_Prisuppdatering_Ej_i_lager.xlsx",
        )

    def test_supplier_exports_use_expected_columns_per_category(self) -> None:
        sku_col = HICORE_COLUMNS["sku"]
        name_col = HICORE_COLUMNS["name"]
        brand_col = HICORE_COLUMNS["brand"]
        supplier_col = HICORE_COLUMNS["supplier"]
        total_col = HICORE_COLUMNS["total_stock"]
        reserved_col = HICORE_COLUMNS["reserved"]
        price_col = HICORE_COLUMNS["price"]
        purchase_col = _purchase_column_name()

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
        hicore_bytes = _to_csv_bytes(df_hicore)

        supplier_columns = [*SUPPLIER_HICORE_RENAME_COLUMNS, SUPPLIER_HICORE_SUPPLIER_COLUMN]
        base_row = {column: "" for column in supplier_columns}
        df_supplier = pd.DataFrame(
            [
                {
                    **base_row,
                    sku_col: "100",
                    name_col: "SKU 100 supplier",
                    brand_col: "Brand 100",
                    purchase_col: "5",
                    price_col: "11",
                    SUPPLIER_HICORE_SUPPLIER_COLUMN: "EM Nordic",
                },
                {
                    **base_row,
                    sku_col: "200",
                    name_col: "SKU 200 supplier",
                    brand_col: "Brand 200",
                    purchase_col: "8",
                    price_col: "21",
                    SUPPLIER_HICORE_SUPPLIER_COLUMN: "EM Nordic",
                },
                {
                    **base_row,
                    sku_col: "400",
                    name_col: "SKU 400 supplier",
                    brand_col: "Brand 400",
                    purchase_col: "12",
                    price_col: "40",
                    SUPPLIER_HICORE_SUPPLIER_COLUMN: "EM Nordic",
                },
            ]
        )
        result = compute_supplier_result(
            hicore_bytes=hicore_bytes,
            supplier_name="EM Nordic",
            supplier_df=df_supplier,
        )

        outgoing_export = _read_excel_bytes(result.outgoing_excel_bytes)
        self.assertEqual(outgoing_export.columns.tolist(), [sku_col])
        self.assertEqual(outgoing_export[sku_col].tolist(), ["00300"])

        new_products_export = _read_excel_bytes(result.new_products_excel_bytes)
        self.assertEqual(new_products_export.columns.tolist(), supplier_columns)
        self.assertEqual(new_products_export[sku_col].tolist(), ["400"])

        out_of_stock_export = _read_excel_bytes(result.price_updates_out_of_stock_excel_bytes)
        self.assertEqual(
            out_of_stock_export.columns.tolist(),
            [sku_col, purchase_col, price_col, brand_col],
        )
        self.assertEqual(out_of_stock_export[sku_col].tolist(), ["00100"])
        self.assertEqual(out_of_stock_export[purchase_col].tolist(), ["5"])
        self.assertEqual(out_of_stock_export[price_col].tolist(), ["11"])
        self.assertEqual(out_of_stock_export[brand_col].tolist(), ["Brand 100"])

        in_stock_export = _read_excel_bytes(result.price_updates_in_stock_excel_bytes)
        self.assertEqual(
            in_stock_export.columns.tolist(),
            [sku_col, purchase_col, price_col, brand_col],
        )
        self.assertEqual(in_stock_export[sku_col].tolist(), ["00200"])
        self.assertEqual(in_stock_export[purchase_col].tolist(), ["8"])
        self.assertEqual(in_stock_export[price_col].tolist(), ["21"])
        self.assertEqual(in_stock_export[brand_col].tolist(), ["Brand 200"])

    def test_supplier_compare_applies_profile_transform_and_brand_filter(self) -> None:
        sku_col = HICORE_COLUMNS["sku"]
        name_col = HICORE_COLUMNS["name"]
        supplier_col = HICORE_COLUMNS["supplier"]
        total_col = HICORE_COLUMNS["total_stock"]
        reserved_col = HICORE_COLUMNS["reserved"]
        price_col = HICORE_COLUMNS["price"]

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
                    total_col: "1",
                    reserved_col: "0",
                    price_col: "20",
                    supplier_col: "EM Nordic",
                },
            ]
        )
        hicore_bytes = _to_csv_bytes(df_hicore)

        df_supplier = pd.DataFrame(
            [
                {
                    "SupplierSku": "100",
                    "Short Description": "Speaker",
                    "Brand": "Sony",
                    "Cost": "5",
                    "Price": "11",
                },
                {
                    "SupplierSku": "400",
                    "Short Description": "Headphones",
                    "Brand": "Sony",
                    "Cost": "12",
                    "Price": "40",
                },
                {
                    "SupplierSku": "500",
                    "Short Description": "Amp",
                    "Brand": " ACME ",
                    "Cost": "9",
                    "Price": "30",
                },
            ]
        )
        prepare_analysis = build_supplier_prepare_analysis(
            df_supplier,
            supplier_name="EM Nordic",
            profile_mapping={
                "Art.m\u00e4rkning": "SupplierSku",
                "Varum\u00e4rke": "Brand",
                "Ink\u00f6pspris": "Cost",
                "UtprisInklMoms": "Price",
            },
            profile_composite_fields={
                "Artikelnamn": ["Short Description", "Brand"],
            },
            profile_filters={
                "brand_source_column": "Brand",
                "excluded_brand_values": ["acme"],
            },
        )
        prepared_supplier_df = finalize_supplier_prepare_analysis(
            prepare_analysis,
            selected_candidates={},
        )

        result = compute_supplier_result(
            hicore_bytes=hicore_bytes,
            supplier_name="EM Nordic",
            supplier_df=prepared_supplier_df,
        )

        self.assertEqual(result.new_products_count, 1)
        self.assertEqual(result.new_products_df["sku"].tolist(), ["400"])
        self.assertEqual(result.new_products_df["name"].tolist(), ["Headphones Sony"])
        self.assertEqual(result.price_updates_out_of_stock_count, 1)
        self.assertEqual(result.price_updates_out_of_stock_df["sku"].tolist(), ["100", "100"])
        self.assertNotIn("side", result.price_updates_out_of_stock_df.columns.tolist())
        self.assertEqual(result.price_updates_out_of_stock_df["source"].tolist(), ["hicore", "supplier"])

    def test_supplier_compare_moves_article_number_match_to_review_bucket(self) -> None:
        sku_col = HICORE_COLUMNS["sku"]
        article_number_col = HICORE_COLUMNS["article_number"]
        name_col = HICORE_COLUMNS["name"]
        supplier_col = HICORE_COLUMNS["supplier"]
        total_col = HICORE_COLUMNS["total_stock"]
        reserved_col = HICORE_COLUMNS["reserved"]
        price_col = HICORE_COLUMNS["price"]

        df_hicore = pd.DataFrame(
            [
                {
                    sku_col: "OLD-1",
                    article_number_col: "ART-9",
                    name_col: "SKU old",
                    total_col: "1",
                    reserved_col: "0",
                    price_col: "10",
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
                    sku_col: "NEW-1",
                    article_number_col: "ART-9",
                    name_col: "SKU new",
                    price_col: "10",
                    SUPPLIER_HICORE_SUPPLIER_COLUMN: "EM Nordic",
                },
            ]
        )

        result = compute_supplier_result(
            hicore_bytes=hicore_bytes,
            supplier_name="EM Nordic",
            supplier_df=df_supplier,
        )

        self.assertEqual(result.outgoing_count, 0)
        self.assertEqual(result.new_products_count, 0)
        self.assertEqual(result.article_number_review_count, 1)
        self.assertNotIn("reason", result.article_number_review_df.columns.tolist())
        self.assertNotIn("side", result.article_number_review_df.columns.tolist())
        self.assertEqual(result.article_number_review_df["source"].tolist(), ["hicore", "supplier"])
        review_export = _read_excel_bytes(result.article_number_review_excel_bytes)
        self.assertEqual(review_export.columns.tolist(), [sku_col, article_number_col, name_col])
        self.assertEqual(review_export[sku_col].tolist(), ["NEW-1"])
        self.assertEqual(review_export[article_number_col].tolist(), ["ART-9"])
        self.assertEqual(review_export[name_col].tolist(), ["SKU new"])

    def test_supplier_exports_force_text_format_for_identifier_columns(self) -> None:
        sku_col = HICORE_COLUMNS["sku"]
        article_number_col = HICORE_COLUMNS["article_number"]
        name_col = HICORE_COLUMNS["name"]
        supplier_col = HICORE_COLUMNS["supplier"]
        total_col = HICORE_COLUMNS["total_stock"]
        reserved_col = HICORE_COLUMNS["reserved"]
        price_col = HICORE_COLUMNS["price"]

        df_hicore = pd.DataFrame(
            [
                {
                    sku_col: "00100",
                    article_number_col: "0009",
                    name_col: "SKU old",
                    total_col: "1",
                    reserved_col: "0",
                    price_col: "10",
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
                    article_number_col: "0009",
                    name_col: "SKU supplier",
                    price_col: "11",
                    SUPPLIER_HICORE_SUPPLIER_COLUMN: "EM Nordic",
                },
            ]
        )

        result = compute_supplier_result(
            hicore_bytes=hicore_bytes,
            supplier_name="EM Nordic",
            supplier_df=df_supplier,
        )

        price_workbook = _load_excel_workbook(result.price_updates_in_stock_excel_bytes)
        price_sheet = price_workbook.active
        self.assertEqual(price_sheet["A1"].value, sku_col)
        self.assertEqual(price_sheet["A2"].value, "00100")
        self.assertEqual(price_sheet["A2"].number_format, "@")

        review_hicore = pd.DataFrame(
            [
                {
                    sku_col: "OLD-1",
                    article_number_col: "0009",
                    name_col: "SKU old",
                    total_col: "1",
                    reserved_col: "0",
                    price_col: "10",
                    supplier_col: "EM Nordic",
                },
            ]
        )
        review_hicore_bytes = _to_csv_bytes(review_hicore)
        review_supplier = pd.DataFrame(
            [
                {
                    **base_row,
                    sku_col: "NEW-1",
                    article_number_col: "0009",
                    name_col: "SKU new",
                    price_col: "10",
                    SUPPLIER_HICORE_SUPPLIER_COLUMN: "EM Nordic",
                },
            ]
        )
        review_result = compute_supplier_result(
            hicore_bytes=review_hicore_bytes,
            supplier_name="EM Nordic",
            supplier_df=review_supplier,
        )

        review_workbook = _load_excel_workbook(review_result.article_number_review_excel_bytes)
        review_sheet = review_workbook.active
        self.assertEqual(review_sheet["A1"].value, sku_col)
        self.assertEqual(review_sheet["A2"].value, "NEW-1")
        self.assertEqual(review_sheet["A2"].number_format, "@")
        self.assertEqual(review_sheet["B1"].value, article_number_col)
        self.assertEqual(review_sheet["B2"].value, "0009")
        self.assertEqual(review_sheet["B2"].number_format, "@")

    def test_supplier_price_exports_write_decimal_columns_as_numeric_cells(self) -> None:
        sku_col = HICORE_COLUMNS["sku"]
        name_col = HICORE_COLUMNS["name"]
        brand_col = HICORE_COLUMNS["brand"]
        supplier_col = HICORE_COLUMNS["supplier"]
        total_col = HICORE_COLUMNS["total_stock"]
        reserved_col = HICORE_COLUMNS["reserved"]
        price_col = HICORE_COLUMNS["price"]
        purchase_col = _purchase_column_name()

        df_hicore = pd.DataFrame(
            [
                {
                    sku_col: "00100",
                    name_col: "SKU 100",
                    total_col: "3",
                    reserved_col: "0",
                    price_col: "10",
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
                    brand_col: "Brand 100",
                    purchase_col: "12,50 SEK",
                    price_col: "99.95",
                    SUPPLIER_HICORE_SUPPLIER_COLUMN: "EM Nordic",
                },
            ]
        )

        result = compute_supplier_result(
            hicore_bytes=hicore_bytes,
            supplier_name="EM Nordic",
            supplier_df=df_supplier,
        )

        workbook = _load_excel_workbook(result.price_updates_in_stock_excel_bytes)
        sheet = workbook.active
        self.assertEqual(sheet["B1"].value, purchase_col)
        self.assertEqual(sheet["B2"].data_type, "n")
        self.assertEqual(sheet["B2"].value, 12.5)
        self.assertEqual(sheet["C1"].value, price_col)
        self.assertEqual(sheet["C2"].data_type, "n")
        self.assertEqual(sheet["C2"].value, 99.95)

    def test_supplier_compare_does_not_mark_profile_excluded_brand_as_outgoing(self) -> None:
        sku_col = HICORE_COLUMNS["sku"]
        name_col = HICORE_COLUMNS["name"]
        brand_col = HICORE_COLUMNS["brand"]
        supplier_col = HICORE_COLUMNS["supplier"]
        total_col = HICORE_COLUMNS["total_stock"]
        reserved_col = HICORE_COLUMNS["reserved"]
        price_col = HICORE_COLUMNS["price"]

        df_hicore = pd.DataFrame(
            [
                {
                    sku_col: "100",
                    name_col: "SKU 100",
                    brand_col: "Sony",
                    total_col: "0",
                    reserved_col: "0",
                    price_col: "10",
                    supplier_col: "EM Nordic",
                },
                {
                    sku_col: "500",
                    name_col: "SKU 500",
                    brand_col: "ACME",
                    total_col: "0",
                    reserved_col: "0",
                    price_col: "30",
                    supplier_col: "EM Nordic",
                },
            ]
        )
        hicore_bytes = _to_csv_bytes(df_hicore)

        df_supplier = pd.DataFrame(
            [
                {
                    "SupplierSku": "100",
                    "Short Description": "Speaker",
                    "Brand": "Sony",
                    "Cost": "5",
                    "Price": "11",
                },
                {
                    "SupplierSku": "500",
                    "Short Description": "Amp",
                    "Brand": " ACME ",
                    "Cost": "9",
                    "Price": "30",
                },
            ]
        )
        prepare_analysis = build_supplier_prepare_analysis(
            df_supplier,
            supplier_name="EM Nordic",
            profile_mapping={
                "Art.m\u00e4rkning": "SupplierSku",
                "Varum\u00e4rke": "Brand",
                "Ink\u00f6pspris": "Cost",
                "UtprisInklMoms": "Price",
            },
            profile_composite_fields={
                "Artikelnamn": ["Short Description", "Brand"],
            },
            profile_filters={
                "brand_source_column": "Brand",
                "excluded_brand_values": ["acme"],
            },
        )
        prepared_supplier_df = finalize_supplier_prepare_analysis(
            prepare_analysis,
            selected_candidates={},
        )

        result = compute_supplier_result(
            hicore_bytes=hicore_bytes,
            supplier_name="EM Nordic",
            supplier_df=prepared_supplier_df,
            profile_excluded_normalized_skus=set(prepare_analysis.excluded_normalized_skus),
        )

        self.assertEqual(result.outgoing_count, 0)
        self.assertTrue(result.outgoing_df.empty)


if __name__ == "__main__":
    unittest.main()
