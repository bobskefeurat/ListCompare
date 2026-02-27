import unittest

import pandas as pd

from listcompare.interfaces.ui_app import (
    _build_supplier_hicore_renamed_copy,
    _matches_profile_output_format,
    _missing_profile_source_columns,
    _profile_has_required_sku_mapping,
)


class SupplierTransformOptionTests(unittest.TestCase):
    def test_profile_requires_art_markning_mapping_for_sku(self) -> None:
        self.assertTrue(_profile_has_required_sku_mapping({"Art.m\u00e4rkning": "SupplierSku"}))
        self.assertFalse(_profile_has_required_sku_mapping({"Lev.artnr": "SupplierSku"}))

    def test_missing_profile_source_columns_detects_unavailable_columns(self) -> None:
        missing = _missing_profile_source_columns(
            {
                "Art.m\u00e4rkning": "SupplierSku",
                "Artikelnamn": "NameCol",
            },
            ["SupplierSku"],
        )
        self.assertEqual(missing, ["NameCol"])

    def test_build_supplier_transform_can_strip_leading_zeros_from_sku(self) -> None:
        df_supplier = pd.DataFrame(
            {
                "SupplierSku": ["00123", "00045", "A99"],
                "NameCol": ["P1", "P2", "P3"],
            }
        )

        renamed = _build_supplier_hicore_renamed_copy(
            df_supplier,
            target_to_source={
                "Art.m\u00e4rkning": "SupplierSku",
                "Artikelnamn": "NameCol",
            },
            supplier_name="EM Nordic",
            strip_leading_zeros_from_sku=True,
        )

        self.assertEqual(renamed["Art.m\u00e4rkning"].tolist(), ["123", "45", "A99"])
        self.assertTrue((renamed["Leverant\u00f6r"] == "EM Nordic").all())

    def test_build_supplier_transform_can_ignore_rows_without_sku(self) -> None:
        df_supplier = pd.DataFrame(
            {
                "SupplierSku": ["00123", "", None, "   ", "0000"],
                "NameCol": ["P1", "P2", "P3", "P4", "P5"],
            }
        )

        renamed = _build_supplier_hicore_renamed_copy(
            df_supplier,
            target_to_source={
                "Art.m\u00e4rkning": "SupplierSku",
                "Artikelnamn": "NameCol",
            },
            supplier_name="EM Nordic",
            strip_leading_zeros_from_sku=True,
            ignore_rows_missing_sku=True,
        )

        self.assertEqual(renamed["Art.m\u00e4rkning"].tolist(), ["123", "0"])
        self.assertEqual(len(renamed), 2)

    def test_profile_output_format_requires_mapped_targets_and_supplier_column(self) -> None:
        mapping = {
            "Art.m\u00e4rkning": "SupplierSku",
            "Artikelnamn": "NameCol",
        }
        self.assertTrue(
            _matches_profile_output_format(
                mapping,
                ["Art.m\u00e4rkning", "Artikelnamn", "Leverant\u00f6r"],
            )
        )

    def test_profile_output_format_is_false_without_supplier_column(self) -> None:
        mapping = {
            "Art.m\u00e4rkning": "SupplierSku",
            "Artikelnamn": "NameCol",
        }
        self.assertFalse(
            _matches_profile_output_format(
                mapping,
                ["Art.m\u00e4rkning", "Artikelnamn"],
            )
        )


if __name__ == "__main__":
    unittest.main()
