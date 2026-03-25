import io
import unittest

import pandas as pd

from listcompare.core.products.product_schema import HICORE_COLUMNS
from listcompare.interfaces.ui.services.compare_pipeline import (
    build_compare_artifacts,
    load_compare_input_data,
)


def _to_csv_bytes(df: pd.DataFrame, *, sep: str) -> bytes:
    return df.to_csv(sep=sep, index=False).encode("utf-8-sig")


def _to_xlsx_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    return buffer.getvalue()


class ComparePipelineTests(unittest.TestCase):
    def test_load_compare_input_data_reads_both_upload_formats(self) -> None:
        df_hicore = pd.DataFrame([{HICORE_COLUMNS["sku"]: "001"}])
        df_magento = pd.DataFrame([{"sku": "1", "qty": "2"}])

        loaded_hicore_df, loaded_magento_df = load_compare_input_data(
            "hicore.csv",
            _to_csv_bytes(df_hicore, sep=";"),
            _to_csv_bytes(df_magento, sep=","),
        )

        self.assertEqual(loaded_hicore_df[HICORE_COLUMNS["sku"]].tolist(), ["001"])
        self.assertEqual(loaded_magento_df["sku"].tolist(), ["1"])

    def test_load_compare_input_data_reads_hicore_excel_upload(self) -> None:
        df_hicore = pd.DataFrame([{HICORE_COLUMNS["sku"]: "001"}])
        df_magento = pd.DataFrame([{"sku": "1", "qty": "2"}])

        loaded_hicore_df, loaded_magento_df = load_compare_input_data(
            "hicore.xlsx",
            _to_xlsx_bytes(df_hicore),
            _to_csv_bytes(df_magento, sep=","),
        )

        self.assertEqual(loaded_hicore_df[HICORE_COLUMNS["sku"]].tolist(), ["001"])
        self.assertEqual(loaded_magento_df["sku"].tolist(), ["1"])

    def test_build_compare_artifacts_collects_export_skus_and_warning(self) -> None:
        sku_col = HICORE_COLUMNS["sku"]
        name_col = HICORE_COLUMNS["name"]
        total_col = HICORE_COLUMNS["total_stock"]
        reserved_col = HICORE_COLUMNS["reserved"]

        df_hicore = pd.DataFrame(
            [
                {
                    sku_col: "001",
                    name_col: "A",
                    total_col: "3",
                    reserved_col: "0",
                }
            ]
        )
        df_magento = pd.DataFrame([{"sku": "2", "name": "B", "qty": "1"}])

        artifacts = build_compare_artifacts(df_hicore, df_magento)

        self.assertEqual(len(artifacts.comparison_results.only_in_magento), 1)
        self.assertEqual(artifacts.only_in_magento_skus, ["2"])
        self.assertEqual(artifacts.only_in_hicore_web_visible_in_stock_skus, [])
        self.assertEqual(
            artifacts.warning_message,
            'HiCore-filen saknar kolumnen "VisaPåWebb". Den nya HiCore-fliken kunde inte beräknas.',
        )


if __name__ == "__main__":
    unittest.main()
