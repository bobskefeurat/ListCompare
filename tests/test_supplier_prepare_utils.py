import unittest

import pandas as pd

from listcompare.core.suppliers.prepare import (
    SUPPLIER_PREPARE_IGNORE_GROUP,
    build_supplier_prepare_analysis,
    finalize_supplier_prepare_analysis,
)


class SupplierPrepareUtilsTests(unittest.TestCase):
    def test_exact_duplicates_are_removed_automatically(self) -> None:
        df_supplier = pd.DataFrame(
            [
                {
                    "SupplierSku": "100",
                    "NameCol": "Speaker",
                    "Price": "11",
                },
                {
                    "SupplierSku": "100",
                    "NameCol": "Speaker",
                    "Price": "11",
                },
            ]
        )

        analysis = build_supplier_prepare_analysis(
            df_supplier,
            supplier_name="EM Nordic",
            profile_mapping={
                "Art.m\u00e4rkning": "SupplierSku",
                "Artikelnamn": "NameCol",
                "UtprisInklMoms": "Price",
            },
        )

        self.assertEqual(analysis.exact_duplicate_rows_removed, 1)
        self.assertEqual(len(analysis.conflicts), 0)

        prepared_df = finalize_supplier_prepare_analysis(
            analysis,
            selected_candidates={},
        )

        self.assertEqual(prepared_df["Art.m\u00e4rkning"].tolist(), ["100"])
        self.assertEqual(prepared_df["Artikelnamn"].tolist(), ["Speaker"])

    def test_conflict_duplicates_require_explicit_selection(self) -> None:
        df_supplier = pd.DataFrame(
            [
                {
                    "SupplierSku": "100",
                    "NameCol": "Speaker",
                    "Price": "11",
                },
                {
                    "SupplierSku": "100",
                    "NameCol": "Speaker",
                    "Price": "11",
                },
                {
                    "SupplierSku": "100",
                    "NameCol": "Speaker",
                    "Price": "12",
                },
            ]
        )

        analysis = build_supplier_prepare_analysis(
            df_supplier,
            supplier_name="EM Nordic",
            profile_mapping={
                "Art.m\u00e4rkning": "SupplierSku",
                "Artikelnamn": "NameCol",
                "UtprisInklMoms": "Price",
            },
        )

        self.assertEqual(analysis.exact_duplicate_rows_removed, 1)
        self.assertEqual(len(analysis.conflicts), 1)
        conflict = analysis.conflicts[0]
        self.assertEqual(len(conflict.candidates), 2)

        with self.assertRaises(ValueError):
            finalize_supplier_prepare_analysis(analysis, selected_candidates={})

        selected_candidate = next(
            candidate
            for candidate in conflict.candidates
            if candidate.row_values["UtprisInklMoms"] == "12"
        )
        prepared_df = finalize_supplier_prepare_analysis(
            analysis,
            selected_candidates={
                conflict.group_key: selected_candidate.candidate_id,
            },
        )

        self.assertEqual(prepared_df["UtprisInklMoms"].tolist(), ["12"])

    def test_existing_output_format_rows_group_by_normalized_sku(self) -> None:
        df_supplier = pd.DataFrame(
            [
                {
                    "Art.m\u00e4rkning": "00123",
                    "Artikelnamn": "Receiver",
                    "Leverant\u00f6r": "EM Nordic",
                },
                {
                    "Art.m\u00e4rkning": "123",
                    "Artikelnamn": "Receiver",
                    "Leverant\u00f6r": "EM Nordic",
                },
            ]
        )

        analysis = build_supplier_prepare_analysis(
            df_supplier,
            supplier_name="EM Nordic",
            profile_mapping={
                "Art.m\u00e4rkning": "SupplierSku",
            },
        )

        self.assertEqual(analysis.exact_duplicate_rows_removed, 1)
        prepared_df = finalize_supplier_prepare_analysis(
            analysis,
            selected_candidates={},
        )

        self.assertEqual(len(prepared_df), 1)
        self.assertEqual(prepared_df["Artikelnamn"].tolist(), ["Receiver"])

    def test_conflict_group_can_be_ignored(self) -> None:
        df_supplier = pd.DataFrame(
            [
                {
                    "SupplierSku": "100",
                    "NameCol": "Speaker",
                    "Price": "11",
                },
                {
                    "SupplierSku": "100",
                    "NameCol": "Speaker Bundle",
                    "Price": "21",
                },
                {
                    "SupplierSku": "200",
                    "NameCol": "Receiver",
                    "Price": "31",
                },
            ]
        )

        analysis = build_supplier_prepare_analysis(
            df_supplier,
            supplier_name="EM Nordic",
            profile_mapping={
                "Art.m\u00e4rkning": "SupplierSku",
                "Artikelnamn": "NameCol",
                "UtprisInklMoms": "Price",
            },
        )

        self.assertEqual(len(analysis.conflicts), 1)

        prepared_df = finalize_supplier_prepare_analysis(
            analysis,
            selected_candidates={
                analysis.conflicts[0].group_key: SUPPLIER_PREPARE_IGNORE_GROUP,
            },
        )

        self.assertEqual(prepared_df["Art.m\u00e4rkning"].tolist(), ["200"])

    def test_existing_output_format_applies_brand_filter_and_collects_excluded_skus(self) -> None:
        df_supplier = pd.DataFrame(
            [
                {
                    "Art.m\u00e4rkning": "100",
                    "Artikelnamn": "Speaker",
                    "Varum\u00e4rke": "Sony",
                    "Leverant\u00f6r": "EM Nordic",
                },
                {
                    "Art.m\u00e4rkning": "500",
                    "Artikelnamn": "Amp",
                    "Varum\u00e4rke": " ACME ",
                    "Leverant\u00f6r": "EM Nordic",
                },
            ]
        )

        analysis = build_supplier_prepare_analysis(
            df_supplier,
            supplier_name="EM Nordic",
            profile_mapping={
                "Art.m\u00e4rkning": "SupplierSku",
            },
            profile_filters={
                "brand_source_column": "Brand",
                "excluded_brand_values": ["acme"],
            },
        )

        prepared_df = finalize_supplier_prepare_analysis(
            analysis,
            selected_candidates={},
        )

        self.assertEqual(analysis.excluded_normalized_skus, frozenset({"500"}))
        self.assertEqual(prepared_df["Art.m\u00e4rkning"].tolist(), ["100"])

    def test_existing_output_format_drops_blank_sku_rows(self) -> None:
        df_supplier = pd.DataFrame(
            [
                {
                    "Art.m\u00e4rkning": "",
                    "Artikelnamn": "Blank Row",
                    "Leverant\u00f6r": "EM Nordic",
                },
                {
                    "Art.m\u00e4rkning": "00123",
                    "Artikelnamn": "Receiver",
                    "Leverant\u00f6r": "EM Nordic",
                },
            ]
        )

        analysis = build_supplier_prepare_analysis(
            df_supplier,
            supplier_name="EM Nordic",
            profile_mapping={
                "Art.m\u00e4rkning": "SupplierSku",
            },
        )

        prepared_df = finalize_supplier_prepare_analysis(
            analysis,
            selected_candidates={},
        )

        self.assertEqual(len(analysis.conflicts), 0)
        self.assertEqual(prepared_df["Art.m\u00e4rkning"].tolist(), ["00123"])
        self.assertEqual(prepared_df["Artikelnamn"].tolist(), ["Receiver"])


if __name__ == "__main__":
    unittest.main()
