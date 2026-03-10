from __future__ import annotations

import pandas as pd
import streamlit as st

from ...shared.presentation import with_one_based_index as _with_one_based_index


def render_prepared_supplier_downloads(
    *,
    prepared_excel_bytes: object,
    prepared_file_name: object,
    ignored_rows_excel_bytes: object,
    ignored_rows_file_name: object,
    ignored_rows_df: object,
) -> None:
    st.success("Den ombyggda leverantörsfilen är klar för jämförelse.")
    if isinstance(prepared_excel_bytes, bytes) and str(prepared_file_name).strip() != "":
        st.download_button(
            label="Ladda ner ombyggd leverantörsfil (Excel)",
            data=prepared_excel_bytes,
            file_name=str(prepared_file_name),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_prepared_supplier_excel",
        )
    if (
        isinstance(ignored_rows_excel_bytes, bytes)
        and str(ignored_rows_file_name).strip() != ""
        and isinstance(ignored_rows_df, pd.DataFrame)
        and not ignored_rows_df.empty
    ):
        st.caption(f"Ignorerade rader: {len(ignored_rows_df)}")
        st.download_button(
            label="Ladda ner ignorerade rader (Excel)",
            data=ignored_rows_excel_bytes,
            file_name=str(ignored_rows_file_name),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_supplier_ignored_rows_excel",
        )
        with st.expander("Visa ignorerade rader"):
            st.dataframe(_with_one_based_index(ignored_rows_df), use_container_width=True)
