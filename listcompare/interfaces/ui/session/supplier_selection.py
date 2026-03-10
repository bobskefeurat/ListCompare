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


def sync_selected_supplier_between_views(
    session_state: dict[str, object],
    selected_supplier: Optional[str],
    supplier_options: list[str],
    *,
    target_key: str,
) -> None:
    normalized = normalize_selected_supplier_for_options(selected_supplier, supplier_options)
    if session_state.get(target_key) != normalized:
        session_state[target_key] = normalized
    session_state["_last_supplier_internal_name"] = normalized


def sync_supplier_selection_session_state(
    session_state: dict[str, object],
    supplier_options: list[str],
) -> None:
    normalized_compare_supplier = normalize_selected_supplier_for_options(
        session_state.get("supplier_internal_name"),
        supplier_options,
    )
    canonical_supplier = normalized_compare_supplier
    if session_state.get("supplier_internal_name") != canonical_supplier:
        session_state["supplier_internal_name"] = canonical_supplier
    if session_state.get("supplier_transform_internal_name") != canonical_supplier:
        session_state["supplier_transform_internal_name"] = canonical_supplier
    session_state["_last_supplier_internal_name"] = canonical_supplier
