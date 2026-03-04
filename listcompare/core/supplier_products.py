from collections import defaultdict
from typing import Optional

import pandas as pd

from .product_diff import ProductMap
from .product_model import Product, normalise_price

SUPPLIER_ID_COLUMNS = (
    "EAN",
    "UPC",
    "Art.M\u00e4rkning",
)
SUPPLIER_PRICE_COLUMNS = ("UtprisInklMoms",)
SUPPLIER_NAME_COLUMNS = ("Artikelnamn", "name")


def find_supplier_id_column(
    df_supplier: pd.DataFrame,
    *,
    preferred_columns: tuple[str, ...] = SUPPLIER_ID_COLUMNS,
) -> str:
    normalized = {str(col).strip().casefold(): col for col in df_supplier.columns}
    for wanted in preferred_columns:
        original = normalized.get(wanted.casefold())
        if original is not None:
            return original
    expected = " or ".join(preferred_columns)
    raise ValueError(f'Supplier file must contain column "{expected}".')


def find_supplier_price_column(
    df_supplier: pd.DataFrame,
    *,
    preferred_columns: tuple[str, ...] = SUPPLIER_PRICE_COLUMNS,
) -> str:
    normalized = {str(col).strip().casefold(): col for col in df_supplier.columns}
    for wanted in preferred_columns:
        original = normalized.get(wanted.casefold())
        if original is not None:
            return original
    expected = " or ".join(preferred_columns)
    raise ValueError(f'Supplier file must contain column "{expected}".')


def find_supplier_name_column(
    df_supplier: pd.DataFrame,
    *,
    preferred_columns: tuple[str, ...] = SUPPLIER_NAME_COLUMNS,
) -> Optional[str]:
    normalized = {str(col).strip().casefold(): col for col in df_supplier.columns}
    for wanted in preferred_columns:
        original = normalized.get(wanted.casefold())
        if original is not None:
            return str(original)
    return None


def build_supplier_map(
    df_supplier: pd.DataFrame,
    *,
    preferred_columns: tuple[str, ...] = SUPPLIER_ID_COLUMNS,
    preferred_price_columns: tuple[str, ...] = SUPPLIER_PRICE_COLUMNS,
    preferred_name_columns: tuple[str, ...] = SUPPLIER_NAME_COLUMNS,
) -> ProductMap:
    id_col = find_supplier_id_column(df_supplier, preferred_columns=preferred_columns)
    price_col = find_supplier_price_column(
        df_supplier,
        preferred_columns=preferred_price_columns,
    )
    name_col = find_supplier_name_column(
        df_supplier,
        preferred_columns=preferred_name_columns,
    )
    products: ProductMap = defaultdict(list)

    for _, row in df_supplier.iterrows():
        raw_sku = row.get(id_col, "")
        if pd.isna(raw_sku):
            continue

        sku = str(raw_sku).strip()
        if sku == "" or sku.casefold() == "nan":
            continue
        raw_name = row.get(name_col, "") if name_col is not None else ""
        name = "" if pd.isna(raw_name) else str(raw_name).strip()
        if name.casefold() == "nan":
            name = ""

        products[sku].append(
            Product(
                sku=sku,
                name=name,
                stock="",
                price=normalise_price(row.get(price_col, "")),
                supplier="",
                source="supplier",
            )
        )

    return dict(products)
