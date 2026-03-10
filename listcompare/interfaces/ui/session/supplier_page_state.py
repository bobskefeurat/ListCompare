from __future__ import annotations

from ..common import (
    SUPPLIER_PAGE_VIEW_COMPARE,
    SUPPLIER_PAGE_VIEW_TRANSFORM,
    SUPPLIER_PROFILE_MODE_EDITOR,
    SUPPLIER_PROFILE_MODE_OVERVIEW,
)
from .supplier_selection import normalize_selected_supplier_for_options


def apply_requested_supplier_page_state(
    session_state: dict[str, object],
    *,
    supplier_options: list[str],
) -> None:
    valid_views = (SUPPLIER_PAGE_VIEW_COMPARE, SUPPLIER_PAGE_VIEW_TRANSFORM)

    requested_view = session_state.get("supplier_page_view_request")
    if requested_view in valid_views:
        session_state["supplier_page_view"] = requested_view
    session_state["supplier_page_view_request"] = None

    requested_profile_mode = session_state.get("supplier_profiles_mode_request")
    if requested_profile_mode in (SUPPLIER_PROFILE_MODE_OVERVIEW, SUPPLIER_PROFILE_MODE_EDITOR):
        session_state["supplier_profiles_mode"] = requested_profile_mode
    session_state["supplier_profiles_mode_request"] = None

    requested_profile_supplier = normalize_selected_supplier_for_options(
        session_state.get("supplier_profiles_supplier_request"),
        supplier_options,
    )
    if requested_profile_supplier is not None:
        session_state["supplier_profiles_active_supplier"] = requested_profile_supplier
        session_state["supplier_internal_name"] = requested_profile_supplier
        session_state["supplier_transform_internal_name"] = requested_profile_supplier
    session_state["supplier_profiles_supplier_request"] = None

    if session_state.get("supplier_page_view") not in valid_views:
        session_state["supplier_page_view"] = SUPPLIER_PAGE_VIEW_COMPARE

    previous_rendered_view = session_state.get("supplier_page_view_last_rendered")
    current_view = session_state.get("supplier_page_view")
    if (
        current_view == SUPPLIER_PAGE_VIEW_TRANSFORM
        and previous_rendered_view != SUPPLIER_PAGE_VIEW_TRANSFORM
        and requested_profile_mode != SUPPLIER_PROFILE_MODE_EDITOR
    ):
        session_state["supplier_profiles_mode"] = SUPPLIER_PROFILE_MODE_OVERVIEW
