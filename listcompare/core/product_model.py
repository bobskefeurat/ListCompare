import pandas as pd
from dataclasses import dataclass
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from .repair_magento_export import repair_shifted_magento_rows


# -----------------------------
# Column mappings per source
# -----------------------------

HICORE_COLUMNS = {
    "sku": "Art.märkning",
    "name": "Artikelnamn",
    "stock": "I lager",
    "total_stock": "Totalt lager",
    "reserved": "Reserverade",
    "supplier": "Leverantör",
    "brand": "Varumärke",
}

MAGENTO_COLUMNS = {
    "sku": "sku",
    "name": "name",
    "stock": "qty",
    "supplier": None,
}


# -----------------------------
# Product model
# -----------------------------

@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    stock: str
    supplier: str
    source: str


# -----------------------------
# Helpers
# -----------------------------

def to_str(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalise_stock(value) -> str:

    if pd.isna(value):
        return ""

    s = str(value).strip()
    if s == "":
        return ""

    # remove normal + non-breaking spaces, handle decimal comma
    s2 = s.replace(" ", "").replace("\u00a0", "").replace(",", ".")

    try:
        d = Decimal(s2)
    except InvalidOperation:
        # If not numeric, keep trimmed original text
        return s

    if d == 0:
        return "0"

    # Convert to fixed-point string and trim trailing zeros
    out = format(d, "f")
    if "." in out:
        out = out.rstrip("0").rstrip(".")
    return out


def _to_decimal(value) -> Decimal | None:
    if pd.isna(value):
        return None
    s = str(value).strip()
    if s == "":
        return None
    s2 = s.replace(" ", "").replace("\u00a0", "").replace(",", ".")
    try:
        return Decimal(s2)
    except InvalidOperation:
        return None


def _format_decimal(d: Decimal) -> str:
    if d == 0:
        return "0"
    out = format(d, "f")
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


# -----------------------------
# Core builder
# -----------------------------

def build_product_map(
    df: pd.DataFrame,
    *,
    source: str,
    columns: dict[str, str | None]
) -> dict[str, list[Product]]:

    sku_col = columns["sku"]
    name_col = columns["name"]
    stock_col = columns["stock"]
    total_col = columns.get("total_stock")
    reserved_col = columns.get("reserved")
    supplier_col = columns.get("supplier")

    products: dict[str, list[Product]] = defaultdict(list)

    for _, row in df.iterrows():
        sku = to_str(row.get(sku_col, ""))
        name = to_str(row.get(name_col, ""))
        supplier = to_str(row.get(supplier_col, "")) if supplier_col else ""
        stock_raw = row.get(stock_col, "")
        if source == "hicore" and (total_col or reserved_col):
            total_raw = row.get(total_col, "") if total_col else ""
            reserved_raw = row.get(reserved_col, "") if reserved_col else ""
            stock = compute_hicore_stock(total_raw, reserved_raw)
        else:
            stock = normalise_stock(stock_raw)

        products[sku].append(
            Product(
                sku=sku,
                name=name,
                stock=stock,
                supplier=supplier,
                source=source
            )
        )

    return dict(products)


# -----------------------------
# Public preparation function
# -----------------------------

def prepare_data(df_hicore: pd.DataFrame, df_magento: pd.DataFrame):
    hicore_map = build_product_map(
        df_hicore,
        source="hicore",
        columns=HICORE_COLUMNS
    )

    df_magento_fixed, _n_fixed = repair_shifted_magento_rows(df_magento)
    magento_map = build_product_map(
        df_magento_fixed,
        source="magento",
        columns=MAGENTO_COLUMNS
    )

    # (valfritt) print/logga n_fixed någonstans
    return hicore_map, magento_map

