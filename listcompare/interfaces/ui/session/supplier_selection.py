from __future__ import annotations

from typing import Optional


def normalize_selected_supplier_for_options(
    selected_supplier: object,
    supplier_options: list[str],
) -> Optional[str]:
    if selected_supplier is None:
        return None
    selected = str(selected_supplier).strip()
    if selected == "":
        return None
    return selected if selected in supplier_options else None


def set_selected_supplier(
    session_state: dict[str, object],
    selected_supplier: Optional[str],
    supplier_options: list[str],
) -> Optional[str]:
    normalized = normalize_selected_supplier_for_options(selected_supplier, supplier_options)
    if session_state.get("supplier_internal_name") != normalized:
        session_state["supplier_internal_name"] = normalized
    return normalized


def sync_supplier_selection_session_state(
    session_state: dict[str, object],
    supplier_options: list[str],
) -> None:
    set_selected_supplier(
        session_state,
        session_state.get("supplier_internal_name"),
        supplier_options,
    )
    normalized_last_supplier = normalize_selected_supplier_for_options(
        session_state.get("_last_supplier_internal_name"),
        supplier_options,
    )
    if session_state.get("_last_supplier_internal_name") != normalized_last_supplier:
        session_state["_last_supplier_internal_name"] = normalized_last_supplier
