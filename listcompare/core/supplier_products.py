from collections import defaultdict

import pandas as pd

from .product_diff import ProductMap
from .product_model import Product

SUPPLIER_ID_COLUMNS = (
    "EAN",
    "UPC",
    "Art.M\u00e4rkning",
)


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


def build_supplier_map(
    df_supplier: pd.DataFrame,
    *,
    preferred_columns: tuple[str, ...] = SUPPLIER_ID_COLUMNS,
) -> ProductMap:
    id_col = find_supplier_id_column(df_supplier, preferred_columns=preferred_columns)
    products: ProductMap = defaultdict(list)

    for _, row in df_supplier.iterrows():
        raw_sku = row.get(id_col, "")
        if pd.isna(raw_sku):
            continue

        sku = str(raw_sku).strip()
        if sku == "" or sku.casefold() == "nan":
            continue

        products[sku].append(
            Product(
                sku=sku,
                name="",
                stock="",
                supplier="",
                source="supplier",
            )
        )

    return dict(products)
