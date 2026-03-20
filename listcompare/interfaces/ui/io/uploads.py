from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st
from openpyxl import load_workbook

from ..common import CSV_ENCODINGS


def _uploaded_csv_to_df(
    data: bytes,
    *,
    sep: str | None,
    engine: Optional[str] = None,
    extra_read_csv_kwargs: Optional[dict[str, object]] = None,
) -> pd.DataFrame:
    last_err: Optional[Exception] = None
    for enc in CSV_ENCODINGS:
        try:
            text = data.decode(enc)
            kwargs: dict[str, object] = {
                "sep": sep,
                "dtype": str,
                "index_col": False,
            }
            if engine is not None:
                kwargs["engine"] = engine
            if extra_read_csv_kwargs:
                kwargs.update(extra_read_csv_kwargs)
            return pd.read_csv(io.StringIO(text), **kwargs)
        except UnicodeDecodeError as err:
            last_err = err
        except Exception as err:
            last_err = err
    if last_err is not None:
        raise last_err
    raise UnicodeDecodeError("utf-8", b"", 0, 1, "Unable to decode uploaded CSV")


def _read_supplier_csv_upload(data: bytes) -> pd.DataFrame:
    try:
        return _uploaded_csv_to_df(data, sep=None, engine="python")
    except Exception as first_error:
        fallback_error: Exception = first_error

        for sep in (";", ",", "\t", "|"):
            try:
                return _uploaded_csv_to_df(data, sep=sep, engine="python")
            except Exception as err:
                fallback_error = err

        for sep in (";", ",", "\t", "|"):
            try:
                return _uploaded_csv_to_df(
                    data,
                    sep=sep,
                    engine="python",
                    extra_read_csv_kwargs={
                        # Fallback for malformed CSV quotes in some supplier exports.
                        "quoting": csv.QUOTE_NONE,
                    },
                )
            except Exception as err:
                fallback_error = err

        raise ValueError(
            "Kunde inte l\u00e4sa CSV-filen. Filen verkar inneh\u00e5lla trasig CSV-formatering "
            f"(t.ex. citattecken). Originalfel: {first_error}. Senaste fallback-fel: {fallback_error}"
        ) from first_error


def _read_compare_magento_csv_upload(data: bytes) -> pd.DataFrame:
    return _read_supplier_csv_upload(data)


def _zero_pad_width_from_excel_number_format(number_format: object) -> Optional[int]:
    text = str(number_format or "").strip()
    if text == "":
        return None

    primary_section = text.split(";", 1)[0]
    primary_section = re.sub(r'"[^"]*"', "", primary_section)
    primary_section = re.sub(r"\[[^\]]*\]", "", primary_section)
    primary_section = re.sub(r"\\.", "", primary_section)
    primary_section = primary_section.strip()
    if re.fullmatch(r"0+", primary_section) is None:
        return None
    return len(primary_section)


def _formatted_zero_padded_excel_text(raw_value: object, number_format: object) -> Optional[str]:
    width = _zero_pad_width_from_excel_number_format(number_format)
    if width is None or isinstance(raw_value, bool):
        return None
    if isinstance(raw_value, int):
        integer_value = raw_value
    elif isinstance(raw_value, float):
        if not raw_value.is_integer():
            return None
        integer_value = int(raw_value)
    else:
        return None

    sign = "-" if integer_value < 0 else ""
    digits = str(abs(integer_value)).zfill(width)
    return f"{sign}{digits}"


def _read_excel_upload(data: bytes) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(data), dtype=str)
    workbook = load_workbook(io.BytesIO(data), data_only=True)
    try:
        worksheet = workbook[workbook.sheetnames[0]]
        repaired_df = df.copy()
        for row_index in range(len(repaired_df.index)):
            for column_index in range(len(repaired_df.columns)):
                cell = worksheet.cell(row=row_index + 2, column=column_index + 1)
                repaired_value = _formatted_zero_padded_excel_text(
                    cell.value,
                    cell.number_format,
                )
                if repaired_value is None:
                    continue
                repaired_df.iat[row_index, column_index] = repaired_value
        return repaired_df
    finally:
        workbook.close()


def _read_supplier_upload(file_name: str, data: bytes) -> pd.DataFrame:
    return _read_supplier_upload_cached(file_name=file_name, data=data).copy()


@st.cache_data(show_spinner=False)
def _read_supplier_upload_cached(file_name: str, data: bytes) -> pd.DataFrame:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".csv":
        return _read_supplier_csv_upload(data)
    if suffix in (".xlsx", ".xls", ".xlsm"):
        return _read_excel_upload(data)
    raise ValueError(f"Unsupported supplier file type: {file_name}")
