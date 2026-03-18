from __future__ import annotations

from typing import Optional

import pandas as pd

from ....core.comparison import SupplierArticleNumberReviewMatch
from ....core.products.product_diff import ProductMap, normalize_sku
from ....core.products.product_schema import HICORE_COLUMNS, Product


def _product_map_to_df(product_map: ProductMap) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for key in sorted(product_map.keys(), key=lambda value: (normalize_sku(str(value)), str(value))):
        products = product_map[key]
        for product in products:
            rows.append(
                {
                    "map_key": key,
                    "sku": product.sku,
                    "name": product.name,
                    "stock": product.stock,
                    "price": product.price,
                    "supplier": product.supplier,
                    "source": product.source,
                }
            )

    if not rows:
        return pd.DataFrame(columns=["map_key", "sku", "name", "stock", "price", "supplier", "source"])
    df = pd.DataFrame(rows)
    df["_lc_sort_sku"] = df["sku"].map(lambda value: normalize_sku(str(value).strip()))
    df["_lc_sort_sku_raw"] = df["sku"].map(lambda value: str(value).strip())
    df = df.sort_values(by=["_lc_sort_sku", "_lc_sort_sku_raw"], kind="stable")
    df = df.drop(columns=["_lc_sort_sku", "_lc_sort_sku_raw"])
    return df.reset_index(drop=True)


def _mismatch_map_to_df(
    mismatch_map: dict[str, dict[str, list[Product]]],
    *,
    preferred_side_order: tuple[str, ...] = ("hicore", "magento", "supplier"),
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    side_rank = {side_name: rank for rank, side_name in enumerate(preferred_side_order)}
    for normalized_sku in sorted(mismatch_map.keys(), key=lambda value: (normalize_sku(str(value)), str(value))):
        sides = mismatch_map[normalized_sku]
        ordered_side_names: list[str] = [
            side_name for side_name in preferred_side_order if side_name in sides
        ]
        for side_name in sorted(sides.keys()):
            if side_name not in ordered_side_names:
                ordered_side_names.append(side_name)
        for side_name in ordered_side_names:
            for product in sides.get(side_name, []):
                rows.append(
                    {
                        "normalized_sku": normalized_sku,
                        "_lc_side_rank": side_rank.get(str(side_name), len(side_rank)),
                        "sku": product.sku,
                        "name": product.name,
                        "stock": product.stock,
                        "price": product.price,
                        "supplier": product.supplier,
                        "source": product.source,
                    }
                )

    if not rows:
        return pd.DataFrame(
            columns=["normalized_sku", "sku", "name", "stock", "price", "supplier", "source"]
        )
    df = pd.DataFrame(rows)
    df = df.sort_values(
        by=["normalized_sku", "_lc_side_rank", "sku"],
        kind="stable",
    )
    df = df.drop(columns=["_lc_side_rank"])
    return df.reset_index(drop=True)


def _article_number_review_matches_to_df(
    review_matches: tuple[SupplierArticleNumberReviewMatch, ...],
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    side_rank = {"hicore": 0, "supplier": 1}
    for match in review_matches:
        for side_name, products in (
            ("hicore", list(match.hicore_rows)),
            ("supplier", list(match.supplier_rows)),
        ):
            for product in products:
                rows.append(
                    {
                        "normalized_article_number": match.normalized_article_number,
                        "article_number": (
                            str(product.article_number).strip() or str(match.article_number).strip()
                        ),
                        "_lc_side_rank": side_rank.get(str(side_name), len(side_rank)),
                        "sku": product.sku,
                        "name": product.name,
                        "stock": product.stock,
                        "price": product.price,
                        "supplier": product.supplier,
                        "source": product.source,
                    }
                )

    if not rows:
        return pd.DataFrame(
            columns=[
                "normalized_article_number",
                "article_number",
                "sku",
                "name",
                "stock",
                "price",
                "supplier",
                "source",
            ]
        )

    df = pd.DataFrame(rows)
    df = df.sort_values(
        by=["normalized_article_number", "_lc_side_rank", "sku"],
        kind="stable",
    )
    df = df.drop(columns=["_lc_side_rank"])
    return df.reset_index(drop=True)


def _style_stock_mismatch_df(df: pd.DataFrame):
    if df.empty:
        return df.style

    colors = ("#f3f3f3", "#ffffff")
    row_colors: list[str] = []
    group_column: Optional[str] = None
    for candidate in (
        "normalized_sku",
        "normalized_article_number",
        "article_number",
        "sku",
        HICORE_COLUMNS["sku"],
    ):
        if candidate in df.columns:
            group_column = candidate
            break

    if group_column is not None:
        previous_key: Optional[str] = None
        group_index = -1
        for value in df[group_column].tolist():
            current_key = normalize_sku("" if pd.isna(value) else str(value))
            if previous_key is None or current_key != previous_key:
                group_index += 1
                previous_key = current_key
            row_colors.append(colors[group_index % 2])
    else:
        row_colors = [colors[idx % 2] for idx in range(len(df))]

    index_to_color = dict(zip(df.index.tolist(), row_colors))
    return df.style.apply(
        lambda row: [f"background-color: {index_to_color.get(row.name, colors[1])}"] * len(row),
        axis=1,
    )
