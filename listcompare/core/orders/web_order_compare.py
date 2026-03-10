from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass(frozen=True)
class MagentoOnlyWebOrdersResult:
    preview_df: pd.DataFrame
    export_order_numbers: list[str]
    export_column_name: str
    warning_message: Optional[str]


def _to_clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.casefold() == "nan":
        return ""
    return text


def _find_case_insensitive_column(columns: list[str], wanted: str) -> Optional[str]:
    wanted_folded = str(wanted).strip().casefold()
    for column in columns:
        if str(column).strip().casefold() == wanted_folded:
            return str(column)
    return None


def _normalize_order_number(value: object) -> str:
    text = _to_clean_text(value)
    if text == "":
        return ""
    return text.lstrip("0")


def build_magento_only_web_orders_result(
    df_hicore: pd.DataFrame,
    df_magento: pd.DataFrame,
) -> MagentoOnlyWebOrdersResult:
    hicore_column = _find_case_insensitive_column(df_hicore.columns.tolist(), "Webbordernr")
    if hicore_column is None:
        return MagentoOnlyWebOrdersResult(
            preview_df=pd.DataFrame(columns=df_magento.columns.tolist()),
            export_order_numbers=[],
            export_column_name="ID",
            warning_message='HiCore-filen saknar kolumnen "Webbordernr".',
        )

    magento_column = _find_case_insensitive_column(df_magento.columns.tolist(), "ID")
    if magento_column is None:
        return MagentoOnlyWebOrdersResult(
            preview_df=pd.DataFrame(columns=df_magento.columns.tolist()),
            export_order_numbers=[],
            export_column_name="ID",
            warning_message='Magento-filen saknar kolumnen "ID".',
        )

    hicore_order_numbers = {
        normalized
        for normalized in df_hicore[hicore_column].map(_normalize_order_number).tolist()
        if normalized != ""
    }
    normalized_magento_order_numbers = df_magento[magento_column].map(_normalize_order_number)
    missing_order_mask = normalized_magento_order_numbers.map(
        lambda value: value != "" and value not in hicore_order_numbers
    )
    preview_df = df_magento.loc[missing_order_mask].copy().reset_index(drop=True)

    seen_normalized_order_numbers: set[str] = set()
    export_order_numbers: list[str] = []
    for raw_order_number, normalized_order_number in zip(
        df_magento[magento_column].tolist(),
        normalized_magento_order_numbers.tolist(),
    ):
        if normalized_order_number == "":
            continue
        if normalized_order_number in hicore_order_numbers:
            continue
        if normalized_order_number in seen_normalized_order_numbers:
            continue
        seen_normalized_order_numbers.add(normalized_order_number)
        export_order_numbers.append(_to_clean_text(raw_order_number))

    return MagentoOnlyWebOrdersResult(
        preview_df=preview_df,
        export_order_numbers=export_order_numbers,
        export_column_name=magento_column,
        warning_message=None,
    )
