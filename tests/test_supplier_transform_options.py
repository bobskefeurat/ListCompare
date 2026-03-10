import unittest

import pandas as pd

from listcompare.interfaces.ui.persistence.profile_store import (
    load_profiles,
    save_profiles,
)
from listcompare.core.suppliers.profile import (
    build_supplier_hicore_renamed_copy as _build_supplier_hicore_renamed_copy,
    matches_profile_output_format as _matches_profile_output_format,
    missing_profile_source_columns as _missing_profile_source_columns,
    profile_has_required_sku_mapping as _profile_has_required_sku_mapping,
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

    def test_build_supplier_transform_can_build_composite_article_name(self) -> None:
        df_supplier = pd.DataFrame(
            {
                "SupplierSku": ["00123"],
                "Short Description": ["Speaker"],
                "Brand": ["Sony"],
            }
        )

        renamed = _build_supplier_hicore_renamed_copy(
            df_supplier,
            target_to_source={
                "Art.m\u00e4rkning": "SupplierSku",
                "Varum\u00e4rke": "Brand",
            },
            supplier_name="EM Nordic",
            composite_fields={
                "Artikelnamn": ["Short Description", "Brand"],
            },
        )

        self.assertEqual(renamed["Artikelnamn"].tolist(), ["Speaker Sony"])
        self.assertEqual(renamed["Varum\u00e4rke"].tolist(), ["Sony"])

    def test_build_supplier_transform_can_exclude_brands_from_supplier_column(self) -> None:
        df_supplier = pd.DataFrame(
            {
                "SupplierSku": ["A1", "A2", "A3"],
                "NameCol": ["P1", "P2", "P3"],
                "Brand": ["Sony", "  ACME ", "Yamaha"],
            }
        )

        renamed = _build_supplier_hicore_renamed_copy(
            df_supplier,
            target_to_source={
                "Art.m\u00e4rkning": "SupplierSku",
                "Artikelnamn": "NameCol",
            },
            supplier_name="EM Nordic",
            brand_source_column="Brand",
            excluded_brand_values=["acme"],
        )

        self.assertEqual(renamed["Art.m\u00e4rkning"].tolist(), ["A1", "A3"])

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

    def test_missing_profile_source_columns_includes_composite_and_brand_filter_columns(self) -> None:
        missing = _missing_profile_source_columns(
            {
                "Art.m\u00e4rkning": "SupplierSku",
            },
            ["SupplierSku"],
            composite_fields={"Artikelnamn": ["Short Description", "Brand"]},
            filters={
                "brand_source_column": "Brand",
                "excluded_brand_values": ["Acme"],
            },
        )

        self.assertEqual(missing, ["Brand", "Short Description"])

    def test_profile_output_format_accepts_composite_article_name_target(self) -> None:
        mapping = {
            "Art.m\u00e4rkning": "SupplierSku",
        }
        self.assertTrue(
            _matches_profile_output_format(
                mapping,
                ["Art.m\u00e4rkning", "Artikelnamn", "Leverant\u00f6r"],
                composite_fields={"Artikelnamn": ["Short Description", "Brand"]},
            )
        )

    def test_profile_roundtrip_preserves_composite_fields_and_brand_filters(self) -> None:
        class _InMemoryPath:
            def __init__(self) -> None:
                self._text: str | None = None

            def exists(self) -> bool:
                return self._text is not None

            def write_text(self, text: str, encoding: str = "utf-8") -> int:
                del encoding
                self._text = text
                return len(text)

            def read_text(self, encoding: str = "utf-8-sig") -> str:
                del encoding
                if self._text is None:
                    raise FileNotFoundError
                return self._text

        profile_path = _InMemoryPath()
        save_error = save_profiles(
            profile_path,
            profiles={
                "EM Nordic": {
                    "target_to_source": {
                        "Art.m\u00e4rkning": "SupplierSku",
                        "Varum\u00e4rke": "Brand",
                    },
                    "composite_fields": {
                        "Artikelnamn": ["Short Description", "Brand"],
                    },
                    "filters": {
                        "brand_source_column": "Brand",
                        "excluded_brand_values": ["Acme"],
                    },
                    "options": {
                        "strip_leading_zeros_from_sku": True,
                        "ignore_rows_missing_sku": False,
                    },
                }
            },
        )

        self.assertIsNone(save_error)

        loaded_profiles, load_error = load_profiles(profile_path)

        self.assertIsNone(load_error)
        self.assertEqual(
            loaded_profiles["EM Nordic"]["composite_fields"],
            {"Artikelnamn": ["Short Description", "Brand"]},
        )
        self.assertEqual(
            loaded_profiles["EM Nordic"]["filters"],
            {
                "brand_source_column": "Brand",
                "excluded_brand_values": ["Acme"],
            },
        )


if __name__ == "__main__":
    unittest.main()
