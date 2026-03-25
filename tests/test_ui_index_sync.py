import io
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from listcompare.core.products.product_schema import HICORE_COLUMNS
from listcompare.interfaces.ui.services import index_sync
from listcompare.interfaces.ui.services.shared_sync import SharedSyncStatus


def _xlsx_bytes_from_rows(
    rows: list[list[object]],
    *,
    number_formats: dict[str, str] | None = None,
) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    for row in rows:
        worksheet.append(row)

    for cell_ref, number_format in (number_formats or {}).items():
        worksheet[cell_ref].number_format = number_format

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


class IndexSyncTests(unittest.TestCase):
    def test_sync_index_options_reads_names_from_hicore_excel_upload(self) -> None:
        sku_col = HICORE_COLUMNS["sku"]
        supplier_col = HICORE_COLUMNS["supplier"]
        brand_col = HICORE_COLUMNS["brand"]
        upload_bytes = _xlsx_bytes_from_rows(
            [
                [sku_col, supplier_col, brand_col],
                [123, "EM Nordic", "Sony"],
            ],
            number_formats={"A2": "000000"},
        )
        success_status = SharedSyncStatus(
            level="success",
            message="Synkad",
            shared_folder=r"X:\ListCompareShared",
        )

        with patch.object(
            index_sync,
            "_sync_shared_files",
            side_effect=[success_status, success_status],
        ), patch.object(
            index_sync,
            "_load_suppliers_from_index",
            return_value=(["Acme"], None),
        ), patch.object(
            index_sync,
            "_load_brands_from_index",
            return_value=(["Yamaha"], None),
        ), patch.object(
            index_sync,
            "_save_suppliers_to_index",
        ) as save_suppliers, patch.object(
            index_sync,
            "_save_brands_to_index",
        ) as save_brands, patch.object(
            index_sync,
            "_supplier_index_path",
            return_value=Path("supplier_index.txt"),
        ), patch.object(
            index_sync,
            "_brand_index_path",
            return_value=Path("brand_index.txt"),
        ):
            result = index_sync.sync_index_options_from_uploaded_hicore(
                indexed_suppliers=["Legacy"],
                indexed_brands=["LegacyBrand"],
                stored_hicore_file={"name": "hicore.xlsx", "bytes": upload_bytes},
            )

        self.assertEqual(result.supplier_options, ["Acme", "EM Nordic"])
        self.assertEqual(result.brand_options, ["Sony", "Yamaha"])
        self.assertEqual(result.new_supplier_names, ["EM Nordic"])
        self.assertEqual(result.new_brand_names, ["Sony"])
        self.assertFalse(result.hicore_missing_brand_column)
        self.assertIsNone(result.warning_message)
        save_suppliers.assert_called_once_with(
            Path("supplier_index.txt"),
            ["Acme", "EM Nordic"],
        )
        save_brands.assert_called_once_with(
            Path("brand_index.txt"),
            ["Sony", "Yamaha"],
        )


if __name__ == "__main__":
    unittest.main()
