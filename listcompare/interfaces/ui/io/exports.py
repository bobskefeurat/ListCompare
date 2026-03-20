from __future__ import annotations

import io
from decimal import Decimal, InvalidOperation

import pandas as pd

from ....core.products.product_normalization import normalise_price

TEXT_FORMAT_HEADERS = frozenset({"Art.m\u00e4rkning", "Lev.artnr"})
DECIMAL_FORMAT_HEADERS = frozenset({"Inköpspris", "UtprisInklMoms"})
DECIMAL_NUMBER_FORMAT = "0.################"


def _sku_csv_bytes(skus: list[str]) -> bytes:
    df = pd.DataFrame({"Art.m\u00e4rkning": skus})
    return df.to_csv(sep=";", index=False).encode("utf-8-sig")


def _df_csv_bytes(df: pd.DataFrame, *, sep: str = ";") -> bytes:
    return df.to_csv(sep=sep, index=False).encode("utf-8-sig")


def _df_excel_bytes(df: pd.DataFrame, *, sheet_name: str = "Sheet1") -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        worksheet = writer.book[sheet_name]
        for column_cells in worksheet.iter_cols(min_row=1, max_row=worksheet.max_row):
            header_value = column_cells[0].value
            header_text = str(header_value).strip()
            for cell in column_cells[1:]:
                if cell.value is None:
                    continue
                if header_text in TEXT_FORMAT_HEADERS:
                    cell.number_format = "@"
                    continue
                if header_text in DECIMAL_FORMAT_HEADERS:
                    decimal_value = _coerce_decimal_cell_value(cell.value)
                    if decimal_value is None:
                        continue
                    cell.value = decimal_value
                    cell.number_format = DECIMAL_NUMBER_FORMAT
    return buffer.getvalue()


def _coerce_decimal_cell_value(value: object) -> int | float | None:
    text = str(value).strip()
    if text == "":
        return None

    normalized = normalise_price(text)
    try:
        parsed = Decimal(normalized)
    except (InvalidOperation, ValueError):
        return None

    if parsed == parsed.to_integral():
        return int(parsed)
    return float(parsed)
