import unittest

import pandas as pd

from listcompare.interfaces.ui.io.tables import _style_stock_mismatch_df


class UiTableStyleTests(unittest.TestCase):
    def test_style_stock_mismatch_df_can_group_rows_by_explicit_group_values(self) -> None:
        df = pd.DataFrame(
            [
                {"sku": "OLD-1", "source": "hicore"},
                {"sku": "NEW-1", "source": "supplier"},
                {"sku": "OLD-2", "source": "hicore"},
                {"sku": "NEW-2", "source": "supplier"},
            ]
        )

        styler = _style_stock_mismatch_df(
            df,
            group_values=["ART-9", "ART-9", "ART-10", "ART-10"],
        )
        ctx = styler._compute().ctx

        row_0_color = ctx[(0, 0)][0][1]
        row_1_color = ctx[(1, 0)][0][1]
        row_2_color = ctx[(2, 0)][0][1]
        row_3_color = ctx[(3, 0)][0][1]

        self.assertEqual(row_0_color, row_1_color)
        self.assertNotEqual(row_1_color, row_2_color)
        self.assertEqual(row_2_color, row_3_color)


if __name__ == "__main__":
    unittest.main()
