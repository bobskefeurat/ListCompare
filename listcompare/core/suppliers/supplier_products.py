from collections import defaultdict
from typing import Optional

import pandas as pd

from ..products.product_diff import ProductMap
from ..products.product_normalization import normalise_price
from ..products.product_schema import Product

SUPPLIER_ID_COLUMNS = (
    "EAN",
    "UPC",
    "Art.M\u00e4rkning",
)
SUPPLIER_ARTICLE_NUMBER_COLUMNS = ("Lev.artnr",)
SUPPLIER_PRICE_COLUMNS = ("UtprisInklMoms",)
SUPPLIER_NAME_COLUMNS = ("Artikelnamn", "name")


def _column_values(df_supplier: pd.DataFrame, column_name: Optional[str]) -> list[object]:
    if column_name is None or column_name not in df_supplier.columns:
        return [""] * len(df_supplier.index)
    return df_supplier[column_name].tolist()


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


def find_supplier_article_number_column(
    df_supplier: pd.DataFrame,
    *,
    preferred_columns: tuple[str, ...] = SUPPLIER_ARTICLE_NUMBER_COLUMNS,
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
    article_number_col = find_supplier_article_number_column(df_supplier)
    id_values = _column_values(df_supplier, id_col)
    price_values = _column_values(df_supplier, price_col)
    name_values = _column_values(df_supplier, name_col)
    article_number_values = _column_values(df_supplier, article_number_col)
    products: ProductMap = defaultdict(list)

    normalize_price_value = normalise_price
    for raw_sku, raw_price, raw_name, raw_article_number in zip(
        id_values,
        price_values,
        name_values,
        article_number_values,
    ):
        if pd.isna(raw_sku):
            continue

        sku = str(raw_sku).strip()
        if sku == "" or sku.casefold() == "nan":
            continue
        article_number = "" if pd.isna(raw_article_number) else str(raw_article_number).strip()
        if article_number.casefold() == "nan":
            article_number = ""
        name = "" if pd.isna(raw_name) else str(raw_name).strip()
        if name.casefold() == "nan":
            name = ""

        products[sku].append(
            Product(
                sku=sku,
                article_number=article_number,
                name=name,
                stock="",
                price=normalize_price_value(raw_price),
                supplier="",
                source="supplier",
            )
        )

    return dict(products)
