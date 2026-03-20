from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re

import pandas as pd


def to_str(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalise_stock(value) -> str:
    if pd.isna(value):
        return ""

    raw = str(value).strip()
    if raw == "":
        return ""

    normalized_raw = raw.replace(" ", "").replace("\u00a0", "").replace(",", ".")
    try:
        parsed = Decimal(normalized_raw)
    except InvalidOperation:
        return raw

    if parsed == 0:
        return "0"

    out = format(parsed, "f")
    if "." in out:
        out = out.rstrip("0").rstrip(".")
    return out


def normalise_price(value) -> str:
    if pd.isna(value):
        return ""

    raw = str(value).strip()
    if raw == "":
        return ""

    numeric = re.sub(r"[^0-9,.\-]", "", raw.replace("\u00a0", "").replace(" ", ""))
    if numeric == "":
        return raw

    sign = "-" if numeric.startswith("-") else ""
    unsigned = numeric.replace("-", "")
    if unsigned == "":
        return raw

    if "," in unsigned and "." in unsigned:
        last_comma = unsigned.rfind(",")
        last_dot = unsigned.rfind(".")
        if last_comma > last_dot:
            unsigned = unsigned.replace(".", "").replace(",", ".")
        else:
            unsigned = unsigned.replace(",", "")
    elif "," in unsigned:
        if unsigned.count(",") > 1:
            parts = unsigned.split(",")
            unsigned = "".join(parts[:-1]) + "." + parts[-1]
        else:
            left, right = unsigned.split(",", 1)
            if right.isdigit() and len(right) == 3 and left.isdigit():
                unsigned = left + right
            else:
                unsigned = left + "." + right
    elif "." in unsigned:
        if unsigned.count(".") > 1:
            parts = unsigned.split(".")
            unsigned = "".join(parts[:-1]) + "." + parts[-1]
        else:
            left, right = unsigned.split(".", 1)
            if right.isdigit() and len(right) == 3 and left.isdigit():
                unsigned = left + right

    normalized_numeric = f"{sign}{unsigned}".rstrip(".,")
    if normalized_numeric in ("", "-"):
        return raw

    try:
        parsed = Decimal(normalized_numeric)
    except InvalidOperation:
        return raw

    if parsed == 0:
        return "0"

    out = format(parsed, "f")
    if "." in out:
        out = out.rstrip("0").rstrip(".")
    return out


def _to_decimal(value) -> Decimal | None:
    if pd.isna(value):
        return None
    raw = str(value).strip()
    if raw == "":
        return None
    normalized_raw = raw.replace(" ", "").replace("\u00a0", "").replace(",", ".")
    try:
        return Decimal(normalized_raw)
    except InvalidOperation:
        return None


def _format_decimal(value: Decimal) -> str:
    if value == 0:
        return "0"
    out = format(value, "f")
    if "." in out:
        out = out.rstrip("0").rstrip(".")
    return out


def compute_hicore_stock(total_raw, reserved_raw) -> str:
    total = _to_decimal(total_raw)
    reserved = _to_decimal(reserved_raw)

    if total is None:
        return ""
    if reserved is None:
        reserved = Decimal(0)
    return _format_decimal(total - reserved)


def compute_hicore_stock_with_fallback(total_raw, reserved_raw, stock_raw) -> str:
    computed_stock = compute_hicore_stock(total_raw, reserved_raw)
    if computed_stock != "":
        return computed_stock
    return normalise_stock(stock_raw)
