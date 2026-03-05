from __future__ import annotations

from collections import defaultdict

import pandas as pd

from .product_normalization import compute_hicore_stock, normalise_price, normalise_stock, to_str
from .product_schema import HICORE_COLUMNS, MAGENTO_COLUMNS, Product
from .repair_magento_export import repair_shifted_magento_rows


def build_product_map(
    df: pd.DataFrame,
    *,
    source: str,
    columns: dict[str, str | None],
) -> dict[str, list[Product]]:
    sku_col = columns["sku"]
    name_col = columns["name"]
    stock_col = columns["stock"]
    total_col = columns.get("total_stock")
    reserved_col = columns.get("reserved")
    price_col = columns.get("price")
    supplier_col = columns.get("supplier")

    products: dict[str, list[Product]] = defaultdict(list)
    for _, row in df.iterrows():
        sku = to_str(row.get(sku_col, ""))
        name = to_str(row.get(name_col, ""))
        supplier = to_str(row.get(supplier_col, "")) if supplier_col else ""
        price = normalise_price(row.get(price_col, "")) if price_col else ""

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
                price=price,
                supplier=supplier,
                source=source,
            )
        )

    return dict(products)


def prepare_data(df_hicore: pd.DataFrame, df_magento: pd.DataFrame):
    hicore_map = build_product_map(
        df_hicore,
        source="hicore",
        columns=HICORE_COLUMNS,
    )

    df_magento_fixed, _n_fixed = repair_shifted_magento_rows(df_magento)
    magento_map = build_product_map(
        df_magento_fixed,
        source="magento",
        columns=MAGENTO_COLUMNS,
    )
    return hicore_map, magento_map
