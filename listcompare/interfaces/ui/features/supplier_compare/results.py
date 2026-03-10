from __future__ import annotations

import pandas as pd
import streamlit as st

from listcompare.core.suppliers.profile import safe_filename_part as _safe_filename_part

from ...common import SupplierUiResult
from ...io.tables import _style_stock_mismatch_df
from ...shared.presentation import with_one_based_index as _with_one_based_index


def _supplier_compare_export_file_name(*, supplier_name: str, label: str) -> str:
    safe_supplier = _safe_filename_part(supplier_name)
    safe_label = _safe_filename_part(label).replace(",", "")
    safe_label = "_".join(part for part in safe_label.split("_") if part != "")
    return f"{safe_supplier}_{safe_label}.xlsx"


def _render_supplier_results(result: SupplierUiResult, *, supplier_name: str) -> None:
    if result.warning_message:
        st.warning(result.warning_message)

    outgoing_display_df = result.outgoing_df.drop(columns=["map_key"], errors="ignore")
    new_products_display_df = result.new_products_df.drop(columns=["map_key"], errors="ignore")
    price_updates_out_of_stock_display_df = result.price_updates_out_of_stock_df.drop(
        columns=["normalized_sku", "side"],
        errors="ignore",
    )
    price_updates_in_stock_display_df = result.price_updates_in_stock_df.drop(
        columns=["normalized_sku", "side"],
        errors="ignore",
    )

    metric_col_1, metric_col_2, metric_col_3, metric_col_4 = st.columns(4)
    metric_col_1.metric("Utgående", result.outgoing_count)
    metric_col_2.metric("Nyheter", result.new_products_count)
    metric_col_3.metric("Prisuppdatering, Ej i lager", result.price_updates_out_of_stock_count)
    metric_col_4.metric("Prisuppdatering, I lager", result.price_updates_in_stock_count)

    tab_outgoing, tab_new, tab_price_oos, tab_price_in = st.tabs(
        [
            "Utgående",
            "Nyheter",
            "Prisuppdatering, Ej i lager",
            "Prisuppdatering, I lager",
        ]
    )
    with tab_outgoing:
        st.download_button(
            label="Ladda ner Utgående",
            data=result.outgoing_excel_bytes,
            file_name=_supplier_compare_export_file_name(
                supplier_name=supplier_name,
                label="Utgående",
            ),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_supplier_outgoing_excel",
        )
        st.dataframe(_with_one_based_index(outgoing_display_df), use_container_width=True)
    with tab_new:
        new_products_df = new_products_display_df.drop(columns=["stock"], errors="ignore")
        if "supplier" in new_products_df.columns:
            new_products_df["supplier"] = new_products_df["supplier"].map(
                lambda value: supplier_name if pd.isna(value) or str(value).strip() == "" else value
            )
        else:
            new_products_df["supplier"] = supplier_name
        if "name" in new_products_df.columns and "Artikelnamn" not in new_products_df.columns:
            new_products_df = new_products_df.rename(columns={"name": "Artikelnamn"})
        st.download_button(
            label="Ladda ner Nyheter",
            data=result.new_products_excel_bytes,
            file_name=_supplier_compare_export_file_name(
                supplier_name=supplier_name,
                label="Nyheter",
            ),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_supplier_news_excel",
        )
        st.dataframe(_with_one_based_index(new_products_df), use_container_width=True)
    with tab_price_oos:
        st.download_button(
            label="Ladda ner Prisuppdatering, Ej i lager",
            data=result.price_updates_out_of_stock_excel_bytes,
            file_name=_supplier_compare_export_file_name(
                supplier_name=supplier_name,
                label="Prisuppdatering, Ej i lager",
            ),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_supplier_price_oos_excel",
        )
        st.dataframe(
            _style_stock_mismatch_df(_with_one_based_index(price_updates_out_of_stock_display_df)),
            use_container_width=True,
        )
    with tab_price_in:
        st.download_button(
            label="Ladda ner Prisuppdatering, I lager",
            data=result.price_updates_in_stock_excel_bytes,
            file_name=_supplier_compare_export_file_name(
                supplier_name=supplier_name,
                label="Prisuppdatering, I lager",
            ),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_supplier_price_in_excel",
        )
        st.dataframe(
            _style_stock_mismatch_df(_with_one_based_index(price_updates_in_stock_display_df)),
            use_container_width=True,
        )

