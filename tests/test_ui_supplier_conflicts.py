import unittest

import pandas as pd

from listcompare.core.suppliers.prepare import (
    SUPPLIER_PREPARE_IGNORE_GROUP,
    build_supplier_prepare_analysis,
)
from listcompare.interfaces.ui.features.supplier_compare.conflicts import (
    _ignore_all_conflict_choices,
)
from listcompare.interfaces.ui.features.supplier_compare.prepare import (
    _build_ignored_rows_df,
)


class SupplierConflictUiTests(unittest.TestCase):
    def test_ignore_all_conflict_choices_marks_all_groups_ignored(self) -> None:
        df_supplier = pd.DataFrame(
            [
                {"SupplierSku": "100", "NameCol": "Speaker", "Price": "11"},
                {"SupplierSku": "100", "NameCol": "Speaker Bundle", "Price": "21"},
                {"SupplierSku": "200", "NameCol": "Receiver", "Price": "31"},
                {"SupplierSku": "200", "NameCol": "Receiver Pack", "Price": "32"},
            ]
        )
        analysis = build_supplier_prepare_analysis(
            df_supplier,
            supplier_name="EM Nordic",
            profile_mapping={
                "Art.märkning": "SupplierSku",
                "Artikelnamn": "NameCol",
                "UtprisInklMoms": "Price",
            },
        )

        ignored_choices = _ignore_all_conflict_choices(prepare_analysis=analysis)

        self.assertEqual(
            ignored_choices,
            {
                conflict.group_key: SUPPLIER_PREPARE_IGNORE_GROUP
                for conflict in analysis.conflicts
            },
        )

    def test_ignored_rows_df_only_contains_output_columns(self) -> None:
        df_supplier = pd.DataFrame(
            [
                {"SupplierSku": "100", "NameCol": "Speaker", "Price": "11"},
                {"SupplierSku": "100", "NameCol": "Speaker Bundle", "Price": "21"},
                {"SupplierSku": "200", "NameCol": "Receiver", "Price": "31"},
            ]
        )
        analysis = build_supplier_prepare_analysis(
            df_supplier,
            supplier_name="EM Nordic",
            profile_mapping={
                "Art.märkning": "SupplierSku",
                "Artikelnamn": "NameCol",
                "UtprisInklMoms": "Price",
            },
        )

        ignored_rows_df = _build_ignored_rows_df(
            analysis=analysis,
            selected_candidates={
                analysis.conflicts[0].group_key: SUPPLIER_PREPARE_IGNORE_GROUP,
            },
        )

        self.assertEqual(
            ignored_rows_df.columns.tolist(),
            ["Art.märkning", "Artikelnamn", "UtprisInklMoms", "Leverantör"],
        )
        self.assertEqual(ignored_rows_df["Art.märkning"].tolist(), ["100", "100"])


if __name__ == "__main__":
    unittest.main()
