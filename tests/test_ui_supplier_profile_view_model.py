import unittest

import pandas as pd

from listcompare.core.suppliers.profile import (
    SUPPLIER_TRANSFORM_DEFAULT_FILTERS,
    SUPPLIER_TRANSFORM_DEFAULT_OPTIONS,
)
from listcompare.interfaces.ui.features.supplier_profiles.view_model import (
    selected_supplier_profile_state,
    supplier_file_unique_values,
    supplier_profile_filter_summary,
    supplier_profile_summary_rows,
    supplier_source_preview_state,
)


class SupplierProfileViewModelTests(unittest.TestCase):
    def test_selected_supplier_profile_state_returns_defaults_without_saved_profile(self) -> None:
        result = selected_supplier_profile_state(
            selected_supplier_name="Acme",
            supplier_transform_profiles_raw={},
        )

        self.assertEqual(result.mapping, {})
        self.assertEqual(result.composite_fields, {})
        self.assertEqual(result.filters, dict(SUPPLIER_TRANSFORM_DEFAULT_FILTERS))
        self.assertEqual(result.options, dict(SUPPLIER_TRANSFORM_DEFAULT_OPTIONS))
        self.assertFalse(result.has_saved_profile)

    def test_supplier_profile_summary_rows_include_composite_and_supplier_value(self) -> None:
        rows = supplier_profile_summary_rows(
            selected_supplier_name="Acme",
            profile_mapping={"Art.märkning": "SupplierSku"},
            profile_composite_fields={"Artikelnamn": ["Brand", "Model"]},
        )

        row_by_target = {row["HiCore-kolumn"]: row["Leverantörskolumn"] for row in rows}
        self.assertEqual(row_by_target["Artikelnamn"], "Brand + Model")
        self.assertEqual(row_by_target["Art.märkning"], "SupplierSku")
        self.assertEqual(row_by_target["Leverantör"], "Värde från supplier_index: Acme")

    def test_supplier_profile_filter_summary_returns_none_without_filters(self) -> None:
        self.assertIsNone(supplier_profile_filter_summary(dict(SUPPLIER_TRANSFORM_DEFAULT_FILTERS)))

    def test_supplier_file_unique_values_filters_blank_and_case_duplicates(self) -> None:
        df_supplier = pd.DataFrame({"Brand": ["Sony", " sony ", "", None, "Yamaha", "yamaha"]})

        result = supplier_file_unique_values(df_supplier, column_name="Brand")

        self.assertEqual(result, ["Sony", "Yamaha"])

    def test_supplier_source_preview_state_normalizes_columns_and_detects_duplicates(self) -> None:
        df_supplier = pd.DataFrame([[1, 2]], columns=[" SKU ", "SKU"])

        result = supplier_source_preview_state(df_supplier)

        self.assertEqual(result.source_columns, ["SKU", "SKU"])
        self.assertEqual(result.duplicate_source_columns, ["SKU"])
        self.assertEqual(result.preview_row_count, 1)
        self.assertEqual(result.preview_df.columns.tolist(), ["SKU", "SKU"])


if __name__ == "__main__":
    unittest.main()
