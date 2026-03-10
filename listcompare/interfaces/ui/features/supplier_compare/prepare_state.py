from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from listcompare.core.suppliers.profile import (
    rebuilt_supplier_file_name as _rebuilt_supplier_file_name,
)

from ...io.exports import _df_excel_bytes
from ...session.run_state import clear_supplier_state as _clear_supplier_state


def _ignored_rows_file_name(*, supplier_name: str) -> str:
    rebuilt_name = _rebuilt_supplier_file_name(supplier_name=supplier_name, extension=".xlsx")
    return rebuilt_name.replace("_prislista_", "_ignorerade_rader_", 1)


def _store_prepared_supplier_df(
    *,
    prepared_df: pd.DataFrame,
    ignored_rows_df: pd.DataFrame,
    excluded_normalized_skus: frozenset[str],
    prepare_signature: str,
    supplier_name: str,
) -> None:
    st.session_state["supplier_prepared_df"] = prepared_df
    st.session_state["supplier_prepared_signature"] = prepare_signature
    st.session_state["supplier_prepared_excluded_normalized_skus"] = excluded_normalized_skus
    st.session_state["supplier_prepared_file_name"] = _rebuilt_supplier_file_name(supplier_name)
    st.session_state["supplier_prepared_excel_bytes"] = _df_excel_bytes(
        prepared_df,
        sheet_name="HiCore-format",
    )
    st.session_state["supplier_ignored_rows_df"] = ignored_rows_df
    if ignored_rows_df.empty:
        st.session_state["supplier_ignored_rows_file_name"] = None
        st.session_state["supplier_ignored_rows_excel_bytes"] = None
    else:
        st.session_state["supplier_ignored_rows_file_name"] = _ignored_rows_file_name(
            supplier_name=supplier_name
        )
        st.session_state["supplier_ignored_rows_excel_bytes"] = _df_excel_bytes(
            ignored_rows_df,
            sheet_name="Ignorerade rader",
        )
    st.session_state["supplier_prepare_analysis"] = None
    st.session_state["supplier_prepare_resolution_choices"] = {}


def _sync_supplier_prepare_state(current_signature: Optional[str]) -> None:
    stored_signature = st.session_state.get("supplier_prepared_signature")
    has_pending_analysis = st.session_state.get("supplier_prepare_analysis") is not None
    has_prepared_df = st.session_state.get("supplier_prepared_df") is not None
    if not has_pending_analysis and not has_prepared_df and stored_signature is None:
        return
    if stored_signature != current_signature:
        _clear_supplier_state(st.session_state)

