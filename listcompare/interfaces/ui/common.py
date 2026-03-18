from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin1")

MENU_COMPARE = "J\u00e4mf\u00f6r Hicore/Magento"
MENU_SUPPLIER = "Hantera leverant\u00f6r"
MENU_SETTINGS = "Inst\u00e4llningar"
COMPARE_PAGE_MODE_PRODUCTS = "Produktj\u00e4mf\u00f6relse"
COMPARE_PAGE_MODE_WEB_ORDERS = "Webborder"
SUPPLIER_PAGE_VIEW_COMPARE = "J\u00e4mf\u00f6relse"
SUPPLIER_PAGE_VIEW_TRANSFORM = "Leverant\u00f6rsprofiler"
SUPPLIER_PROFILE_MODE_OVERVIEW = "overview"
SUPPLIER_PROFILE_MODE_EDITOR = "editor"

FILE_STATE_KEYS = {
    "hicore": "stored_hicore_file",
    "magento": "stored_magento_file",
    "compare_web_orders_hicore": "stored_compare_web_orders_hicore_file",
    "compare_web_orders_magento": "stored_compare_web_orders_magento_file",
    "supplier": "stored_supplier_file",
}

UPLOADER_KEYS_BY_KIND = {
    "hicore": ("compare_hicore_uploader", "supplier_hicore_uploader"),
    "magento": ("compare_magento_uploader",),
    "compare_web_orders_hicore": ("compare_web_orders_hicore_uploader",),
    "compare_web_orders_magento": ("compare_web_orders_magento_uploader",),
    "supplier": ("supplier_file_uploader", "supplier_transform_uploader"),
}


@dataclass(frozen=True)
class CompareUiResult:
    only_in_magento_df: pd.DataFrame
    only_in_hicore_web_visible_in_stock_df: pd.DataFrame
    stock_mismatch_df: pd.DataFrame
    only_in_magento_csv_bytes: bytes
    only_in_hicore_web_visible_in_stock_csv_bytes: bytes
    stock_mismatch_csv_bytes: bytes
    only_in_magento_count: int
    only_in_hicore_web_visible_in_stock_count: int
    stock_mismatch_count: int
    warning_message: Optional[str]


@dataclass(frozen=True)
class WebOrderCompareUiResult:
    magento_only_web_orders_df: pd.DataFrame
    magento_only_web_orders_csv_bytes: bytes
    magento_only_web_orders_count: int
    warning_message: Optional[str]


@dataclass(frozen=True)
class SupplierUiResult:
    outgoing_df: pd.DataFrame
    new_products_df: pd.DataFrame
    price_updates_out_of_stock_df: pd.DataFrame
    price_updates_in_stock_df: pd.DataFrame
    article_number_review_df: pd.DataFrame
    outgoing_excel_bytes: bytes
    new_products_excel_bytes: bytes
    price_updates_out_of_stock_excel_bytes: bytes
    price_updates_in_stock_excel_bytes: bytes
    article_number_review_excel_bytes: bytes
    outgoing_count: int
    new_products_count: int
    price_updates_out_of_stock_count: int
    price_updates_in_stock_count: int
    article_number_review_count: int
    warning_message: Optional[str]
