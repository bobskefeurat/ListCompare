import unittest

from listcompare.core.product_model import compute_hicore_stock, normalise_stock


class ProductModelTests(unittest.TestCase):
    def test_normalise_stock_handles_decimal_comma_and_trailing_zeroes(self) -> None:
        self.assertEqual(normalise_stock(" 1,2300 "), "1.23")
        self.assertEqual(normalise_stock("0,00"), "0")

    def test_normalise_stock_keeps_non_numeric_values(self) -> None:
        self.assertEqual(normalise_stock("in stock"), "in stock")
        self.assertEqual(normalise_stock(""), "")

    def test_compute_hicore_stock_subtracts_reserved_from_total(self) -> None:
        self.assertEqual(compute_hicore_stock("12", "2"), "10")
        self.assertEqual(compute_hicore_stock("12,5", "0,5"), "12")
        self.assertEqual(compute_hicore_stock("", "1"), "")


if __name__ == "__main__":
    unittest.main()
