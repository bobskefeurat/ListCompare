from __future__ import annotations

from collections.abc import Callable
from typing import Optional

import streamlit as st

from ..common import (
    SUPPLIER_PAGE_VIEW_TRANSFORM,
    SUPPLIER_PROFILE_MODE_EDITOR,
)


def rerun() -> None:
    rerun_fn = getattr(st, "rerun", None)
    if callable(rerun_fn):
        rerun_fn()
        return
    st.experimental_rerun()


def request_supplier_profile_editor(
    session_state: dict[str, object],
    supplier_name: str,
    *,
    rerun_fn: Optional[Callable[[], None]] = None,
) -> None:
    normalized_supplier_name = str(supplier_name).strip()
    if normalized_supplier_name == "":
        return
    session_state["supplier_page_view_request"] = SUPPLIER_PAGE_VIEW_TRANSFORM
    session_state["supplier_profiles_mode_request"] = SUPPLIER_PROFILE_MODE_EDITOR
    session_state["supplier_profiles_supplier_request"] = normalized_supplier_name
    if rerun_fn is None:
        rerun()
    else:
        rerun_fn()
