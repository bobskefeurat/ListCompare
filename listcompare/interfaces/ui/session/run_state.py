from __future__ import annotations


def clear_compare_state(session_state: dict[str, object]) -> None:
    session_state["compare_ui_result"] = None
    session_state["compare_ui_error"] = None
    session_state["web_order_compare_ui_result"] = None
    session_state["web_order_compare_ui_error"] = None


def clear_supplier_result_state(session_state: dict[str, object]) -> None:
    session_state["supplier_ui_result"] = None
    session_state["supplier_ui_error"] = None


def clear_supplier_prepare_state(session_state: dict[str, object]) -> None:
    session_state["supplier_prepared_df"] = None
    session_state["supplier_prepared_signature"] = None
    session_state["supplier_prepared_file_name"] = None
    session_state["supplier_prepared_excel_bytes"] = None
    session_state["supplier_ignored_rows_df"] = None
    session_state["supplier_ignored_rows_file_name"] = None
    session_state["supplier_ignored_rows_excel_bytes"] = None
    session_state["supplier_prepare_analysis"] = None
    session_state["supplier_prepare_resolution_choices"] = {}


def clear_supplier_state(session_state: dict[str, object]) -> None:
    clear_supplier_result_state(session_state)
    clear_supplier_prepare_state(session_state)


def clear_all_run_state(session_state: dict[str, object]) -> None:
    clear_compare_state(session_state)
    clear_supplier_state(session_state)
