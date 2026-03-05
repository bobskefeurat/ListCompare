import unittest

from listcompare.core.product_normalization import compute_hicore_stock, normalise_price, normalise_stock


class ProductNormalizationTests(unittest.TestCase):
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

    def test_normalise_price_handles_currency_text_and_decimals(self) -> None:
        self.assertEqual(normalise_price("100,00 SEK"), "100")
        self.assertEqual(normalise_price("SEK 1 234,50"), "1234.5")
        self.assertEqual(normalise_price("$1,234.50"), "1234.5")
        self.assertEqual(normalise_price("1.234,00 kr"), "1234")

    def test_normalise_price_keeps_non_numeric_values(self) -> None:
        self.assertEqual(normalise_price("på förfrågan"), "på förfrågan")


if __name__ == "__main__":
    unittest.main()
