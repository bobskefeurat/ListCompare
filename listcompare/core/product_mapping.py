from __future__ import annotations

from collections import defaultdict

import pandas as pd

from .product_normalization import compute_hicore_stock, normalise_price, normalise_stock, to_str
from .product_schema import HICORE_COLUMNS, MAGENTO_COLUMNS, Product
from .repair_magento_export import repair_shifted_magento_rows


def _column_values(df: pd.DataFrame, column_name: str | None) -> list[object]:
    if not column_name or column_name not in df.columns:
        return [""] * len(df.index)
    return df[column_name].tolist()


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

    sku_values = _column_values(df, sku_col)
    name_values = _column_values(df, name_col)
    stock_values = _column_values(df, stock_col)
    total_values = _column_values(df, total_col)
    reserved_values = _column_values(df, reserved_col)
    price_values = _column_values(df, price_col)
    supplier_values = _column_values(df, supplier_col)
    use_hicore_stock_columns = source == "hicore" and (total_col or reserved_col)

    to_str_value = to_str
    normalize_price_value = normalise_price
    normalize_stock_value = normalise_stock
    compute_hicore_stock_value = compute_hicore_stock

    products: dict[str, list[Product]] = defaultdict(list)
    for sku_raw, name_raw, stock_raw, total_raw, reserved_raw, price_raw, supplier_raw in zip(
        sku_values,
        name_values,
        stock_values,
        total_values,
        reserved_values,
        price_values,
        supplier_values,
    ):
        sku = to_str_value(sku_raw)
        name = to_str_value(name_raw)
        supplier = to_str_value(supplier_raw) if supplier_col else ""
        price = normalize_price_value(price_raw) if price_col else ""

        if use_hicore_stock_columns:
            stock = compute_hicore_stock_value(total_raw, reserved_raw)
        else:
            stock = normalize_stock_value(stock_raw)

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
