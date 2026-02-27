from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin1")
SUPPLIER_INDEX_PATH = (Path(__file__).resolve().parents[3] / "supplier_index.txt").resolve()
BRAND_INDEX_PATH = (Path(__file__).resolve().parents[3] / "brand_index.txt").resolve()
UI_SETTINGS_PATH = (Path(__file__).resolve().parents[3] / "ui_settings.json").resolve()
SUPPLIER_TRANSFORM_PROFILES_PATH = (
    Path(__file__).resolve().parents[3] / "supplier_transform_profiles.json"
).resolve()

MENU_COMPARE = "J\u00e4mf\u00f6r Hicore/Magento"
MENU_SUPPLIER = "Hantera leverant\u00f6r"
MENU_SETTINGS = "Inst\u00e4llningar"
SUPPLIER_PAGE_VIEW_COMPARE = "J\u00e4mf\u00f6relse"
SUPPLIER_PAGE_VIEW_TRANSFORM = "Leverant\u00f6rsprofiler"
SUPPLIER_PROFILE_MODE_OVERVIEW = "overview"
SUPPLIER_PROFILE_MODE_EDITOR = "editor"

FILE_STATE_KEYS = {
    "hicore": "stored_hicore_file",
    "magento": "stored_magento_file",
    "supplier": "stored_supplier_file",
}

UPLOADER_KEYS_BY_KIND = {
    "hicore": ("compare_hicore_uploader", "supplier_hicore_uploader"),
    "magento": ("compare_magento_uploader",),
    "supplier": ("supplier_file_uploader", "supplier_transform_uploader"),
}


@dataclass(frozen=True)
class CompareUiResult:
    only_in_magento_df: pd.DataFrame
    stock_mismatch_df: pd.DataFrame
    only_in_magento_csv_bytes: bytes
    stock_mismatch_csv_bytes: bytes
    only_in_magento_count: int
    stock_mismatch_count: int
    warning_message: Optional[str]


@dataclass(frozen=True)
class SupplierUiResult:
    internal_only_df: pd.DataFrame
    internal_only_csv_bytes: bytes
    internal_only_count: int
    warning_message: Optional[str]
