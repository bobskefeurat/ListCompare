from __future__ import annotations

import io

import pandas as pd


def _sku_csv_bytes(skus: list[str]) -> bytes:
    df = pd.DataFrame({"Art.m\u00e4rkning": skus})
    return df.to_csv(sep=";", index=False).encode("utf-8-sig")


def _df_csv_bytes(df: pd.DataFrame, *, sep: str = ";") -> bytes:
    return df.to_csv(sep=sep, index=False).encode("utf-8-sig")


def _df_excel_bytes(df: pd.DataFrame, *, sheet_name: str = "Sheet1") -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()

