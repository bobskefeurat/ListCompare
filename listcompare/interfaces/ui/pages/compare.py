from __future__ import annotations

import streamlit as st

from ..common import (
    COMPARE_PAGE_MODE_PRODUCTS,
    COMPARE_PAGE_MODE_WEB_ORDERS,
    MENU_COMPARE,
    CompareUiResult,
    WebOrderCompareUiResult,
)
from ..io.tables import _style_stock_mismatch_df
from ..shared.presentation import (
    build_progress_updater as _build_progress_updater,
    with_one_based_index as _with_one_based_index,
)
from ..services.compare_compute import (
    compute_compare_result as _compute_compare_result,
    compute_web_order_compare_result as _compute_web_order_compare_result,
)
from ..session.file_inputs import render_file_input as _render_file_input


def _render_product_compare_results(result: CompareUiResult) -> None:
    if result.warning_message:
        st.warning(result.warning_message)

    only_in_magento_display_df = result.only_in_magento_df.drop(
        columns=["map_key", "price", "supplier"],
        errors="ignore",
    )
    stock_mismatch_display_df = result.stock_mismatch_df.drop(
        columns=["normalized_sku", "side"],
        errors="ignore",
    )

    col1, col2 = st.columns(2)
    col1.metric("Unika i Magento", result.only_in_magento_count)
    col2.metric("Lagerdiff", result.stock_mismatch_count)

    download_col1, download_col2 = st.columns(2)
    download_col1.download_button(
        label="Ladda ner only_in_magento_skus.csv",
        data=result.only_in_magento_csv_bytes,
        file_name="only_in_magento_skus.csv",
        mime="text/csv",
        key="download_only_in_magento_csv",
    )
    download_col2.download_button(
        label="Ladda ner stock_mismatch_skus.csv",
        data=result.stock_mismatch_csv_bytes,
        file_name="stock_mismatch_skus.csv",
        mime="text/csv",
        key="download_stock_mismatch_csv",
    )

    tab1, tab2 = st.tabs(["Unika i Magento", "Lagerdiff"])
    with tab1:
        st.dataframe(_with_one_based_index(only_in_magento_display_df), use_container_width=True)
    with tab2:
        st.dataframe(
            _style_stock_mismatch_df(_with_one_based_index(stock_mismatch_display_df)),
            use_container_width=True,
        )


def _render_web_order_compare_results(result: WebOrderCompareUiResult) -> None:
    if result.warning_message:
        st.warning(result.warning_message)

    st.metric("Webborder endast i Magento", result.magento_only_web_orders_count)
    st.download_button(
        label="Ladda ner magento_only_web_order_ids.csv",
        data=result.magento_only_web_orders_csv_bytes,
        file_name="magento_only_web_order_ids.csv",
        mime="text/csv",
        key="download_magento_only_web_orders_csv",
    )
    st.dataframe(
        _with_one_based_index(result.magento_only_web_orders_df),
        use_container_width=True,
    )


def _render_compare_page(*, excluded_brands: list[str]) -> None:
    st.header(MENU_COMPARE)
    selected_mode = st.radio(
        "Jämförelsetyp",
        options=[COMPARE_PAGE_MODE_PRODUCTS, COMPARE_PAGE_MODE_WEB_ORDERS],
        key="compare_page_mode",
        horizontal=True,
    )

    if selected_mode == COMPARE_PAGE_MODE_PRODUCTS:
        st.caption("Ladda upp produktfiler.")
        hicore_file = _render_file_input(
            session_state=st.session_state,
            kind="hicore",
            label="HiCore produkt-export (.csv)",
            file_types=["csv"],
            uploader_key="compare_hicore_uploader",
        )
        magento_file = _render_file_input(
            session_state=st.session_state,
            kind="magento",
            label="Magento produkt-export (.csv)",
            file_types=["csv"],
            uploader_key="compare_magento_uploader",
        )

        if excluded_brands:
            shown_brands = excluded_brands[:8]
            extra_count = len(excluded_brands) - len(shown_brands)
            suffix = f" (+{extra_count} till)" if extra_count > 0 else ""
            st.info(
                f"Exkluderade varumärken: {', '.join(shown_brands)}{suffix}."
            )
        else:
            st.caption("Inga varumärken exkluderas. Ändra i Inställningar vid behov.")

        can_run = hicore_file is not None and magento_file is not None
        if st.button(
            "Kör produktjämförelse",
            type="primary",
            disabled=not can_run,
            key="run_product_compare_button",
        ):
            update_progress, clear_progress = _build_progress_updater(
                label="Produktjämförelse"
            )
            update_progress(0.0, "Startar")
            try:
                result = _compute_compare_result(
                    hicore_bytes=hicore_file["bytes"],  # type: ignore[index]
                    magento_bytes=magento_file["bytes"],  # type: ignore[index]
                    excluded_brands=[str(name) for name in excluded_brands],
                    progress_callback=update_progress,
                )
                update_progress(1.0, "Klar")
                st.session_state["compare_ui_result"] = result
                st.session_state["compare_ui_error"] = None
            except Exception as exc:
                st.session_state["compare_ui_result"] = None
                st.session_state["compare_ui_error"] = str(exc)
            finally:
                clear_progress()

        if st.session_state["compare_ui_error"]:
            st.error(st.session_state["compare_ui_error"])
        if st.session_state["compare_ui_result"] is not None:
            _render_product_compare_results(st.session_state["compare_ui_result"])
        return

    st.caption("Ladda upp webborderfiler.")
    hicore_file = _render_file_input(
        session_state=st.session_state,
        kind="compare_web_orders_hicore",
        label="HiCore webborder-export (.csv)",
        file_types=["csv"],
        uploader_key="compare_web_orders_hicore_uploader",
    )
    magento_file = _render_file_input(
        session_state=st.session_state,
        kind="compare_web_orders_magento",
        label="Magento webborder-export (.csv)",
        file_types=["csv"],
        uploader_key="compare_web_orders_magento_uploader",
    )

    can_run = hicore_file is not None and magento_file is not None
    if st.button(
        "Kör orderjämförelse",
        type="primary",
        disabled=not can_run,
        key="run_web_order_compare_button",
    ):
        update_progress, clear_progress = _build_progress_updater(label="Orderjämförelse")
        update_progress(0.0, "Startar")
        try:
            result = _compute_web_order_compare_result(
                hicore_bytes=hicore_file["bytes"],  # type: ignore[index]
                magento_bytes=magento_file["bytes"],  # type: ignore[index]
                progress_callback=update_progress,
            )
            update_progress(1.0, "Klar")
            st.session_state["web_order_compare_ui_result"] = result
            st.session_state["web_order_compare_ui_error"] = None
        except Exception as exc:
            st.session_state["web_order_compare_ui_result"] = None
            st.session_state["web_order_compare_ui_error"] = str(exc)
        finally:
            clear_progress()

    if st.session_state["web_order_compare_ui_error"]:
        st.error(st.session_state["web_order_compare_ui_error"])
    if st.session_state["web_order_compare_ui_result"] is not None:
        _render_web_order_compare_results(st.session_state["web_order_compare_ui_result"])
