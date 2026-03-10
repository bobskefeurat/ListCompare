import unittest

import pandas as pd

from listcompare.core.suppliers.profile import (
    SUPPLIER_HICORE_NAME_COLUMN,
    SUPPLIER_HICORE_SKU_COLUMN,
    SUPPLIER_TRANSFORM_DEFAULT_FILTERS,
    SUPPLIER_TRANSFORM_DEFAULT_OPTIONS,
)
from listcompare.interfaces.ui.features.supplier_profiles.form_logic import (
    build_profile_preview_artifacts,
    build_current_profile_state,
    build_profile_save_state,
    evaluate_profile_preview,
)


class SupplierProfileFormLogicTests(unittest.TestCase):
    def test_evaluate_profile_preview_blocks_on_duplicate_name_sources(self) -> None:
        result = evaluate_profile_preview(
            selected_supplier_name="Acme",
            target_to_source={SUPPLIER_HICORE_SKU_COLUMN: "sku"},
            composite_fields={SUPPLIER_HICORE_NAME_COLUMN: ["name_1", "name_1"]},
            composite_name_sources=["name_1", "name_1"],
            current_name_mode="composite",
            composite_name_mode="composite",
            current_profile_filters=dict(SUPPLIER_TRANSFORM_DEFAULT_FILTERS),
            strip_leading_zeros_from_sku=False,
            ignore_rows_missing_sku=False,
        )

        self.assertIsNotNone(result.blocking_error)
        self.assertIsNone(result.blocking_info)
        self.assertFalse(result.show_missing_target_info)
        self.assertFalse(result.show_sku_rule_info)

    def test_evaluate_profile_preview_blocks_without_supplier(self) -> None:
        result = evaluate_profile_preview(
            selected_supplier_name="",
            target_to_source={SUPPLIER_HICORE_NAME_COLUMN: "name"},
            composite_fields={},
            composite_name_sources=[],
            current_name_mode="single",
            composite_name_mode="composite",
            current_profile_filters=dict(SUPPLIER_TRANSFORM_DEFAULT_FILTERS),
            strip_leading_zeros_from_sku=False,
            ignore_rows_missing_sku=False,
        )

        self.assertIsNone(result.blocking_error)
        self.assertIsNotNone(result.blocking_info)
        self.assertIn("Leverantör", str(result.blocking_info))

    def test_evaluate_profile_preview_sets_missing_target_and_sku_notice(self) -> None:
        result = evaluate_profile_preview(
            selected_supplier_name="Acme",
            target_to_source={SUPPLIER_HICORE_NAME_COLUMN: "name"},
            composite_fields={},
            composite_name_sources=[],
            current_name_mode="single",
            composite_name_mode="composite",
            current_profile_filters=dict(SUPPLIER_TRANSFORM_DEFAULT_FILTERS),
            strip_leading_zeros_from_sku=True,
            ignore_rows_missing_sku=False,
        )

        self.assertIsNone(result.blocking_error)
        self.assertIsNone(result.blocking_info)
        self.assertTrue(result.show_missing_target_info)
        self.assertTrue(result.show_sku_rule_info)
        self.assertIn(SUPPLIER_HICORE_SKU_COLUMN, result.missing_target_columns)

    def test_build_current_profile_state_normalizes_payload(self) -> None:
        result = build_current_profile_state(
            target_to_source={
                SUPPLIER_HICORE_NAME_COLUMN: "name",
                SUPPLIER_HICORE_SKU_COLUMN: "sku",
            },
            composite_fields={SUPPLIER_HICORE_NAME_COLUMN: []},
            strip_leading_zeros_from_sku=True,
            ignore_rows_missing_sku=False,
        )

        self.assertEqual(
            result.mapping,
            {
                SUPPLIER_HICORE_NAME_COLUMN: "name",
                SUPPLIER_HICORE_SKU_COLUMN: "sku",
            },
        )
        self.assertEqual(result.composite_fields, {})
        self.assertTrue(result.options["strip_leading_zeros_from_sku"])
        self.assertFalse(result.options["ignore_rows_missing_sku"])

    def test_build_profile_save_state_detects_complete_saved_profile(self) -> None:
        current_mapping = {
            SUPPLIER_HICORE_NAME_COLUMN: "name",
            SUPPLIER_HICORE_SKU_COLUMN: "sku",
        }
        current_composite_fields: dict[str, list[str]] = {}
        current_filters = dict(SUPPLIER_TRANSFORM_DEFAULT_FILTERS)
        current_options = dict(SUPPLIER_TRANSFORM_DEFAULT_OPTIONS)

        result = build_profile_save_state(
            selected_supplier_name="Acme",
            supplier_transform_profiles={"Acme": {"target_to_source": current_mapping}},
            saved_profile=current_mapping,
            saved_composite_fields=current_composite_fields,
            saved_filters=current_filters,
            saved_profile_options=current_options,
            current_profile_mapping=current_mapping,
            current_profile_composite_fields=current_composite_fields,
            current_profile_filters=current_filters,
            current_profile_options=current_options,
        )

        self.assertTrue(result.has_saved_complete_profile)
        self.assertEqual(result.save_profile_label, "Uppdatera profil")

    def test_build_profile_preview_artifacts_builds_preview_and_save_state(self) -> None:
        df_supplier = pd.DataFrame(
            {
                "SupplierSku": ["00123"],
                "NameCol": ["Speaker"],
            }
        )

        result = build_profile_preview_artifacts(
            df_supplier=df_supplier,
            selected_supplier_name="Acme",
            supplier_transform_profiles={},
            saved_profile={},
            saved_composite_fields={},
            saved_filters=dict(SUPPLIER_TRANSFORM_DEFAULT_FILTERS),
            saved_profile_options=dict(SUPPLIER_TRANSFORM_DEFAULT_OPTIONS),
            target_to_source={
                SUPPLIER_HICORE_NAME_COLUMN: "NameCol",
                SUPPLIER_HICORE_SKU_COLUMN: "SupplierSku",
            },
            composite_fields={},
            current_profile_filters=dict(SUPPLIER_TRANSFORM_DEFAULT_FILTERS),
            strip_leading_zeros_from_sku=True,
            ignore_rows_missing_sku=False,
        )

        self.assertEqual(result.renamed_df[SUPPLIER_HICORE_NAME_COLUMN].tolist(), ["Speaker"])
        self.assertEqual(result.renamed_df[SUPPLIER_HICORE_SKU_COLUMN].tolist(), ["123"])
        self.assertEqual(result.current_profile_state.mapping[SUPPLIER_HICORE_SKU_COLUMN], "SupplierSku")
        self.assertEqual(result.save_state.save_profile_label, "Spara profil")


if __name__ == "__main__":
    unittest.main()
