from __future__ import annotations

from collections.abc import Callable
from typing import Optional

import streamlit as st

from ..common import FILE_STATE_KEYS, UPLOADER_KEYS_BY_KIND
from .navigation import rerun as _rerun
from .run_state import clear_all_run_state as _clear_all_run_state


def get_stored_file(
    session_state: dict[str, object],
    *,
    kind: str,
) -> Optional[dict[str, object]]:
    stored = session_state.get(FILE_STATE_KEYS[kind])
    if isinstance(stored, dict):
        return stored
    return None


def store_uploaded_file(
    session_state: dict[str, object],
    *,
    kind: str,
    uploaded_file,
    clear_all_run_state: Optional[Callable[[], None]] = None,
) -> None:
    session_state[FILE_STATE_KEYS[kind]] = {
        "name": uploaded_file.name,
        "bytes": uploaded_file.getvalue(),
    }
    if clear_all_run_state is None:
        _clear_all_run_state(session_state)
    else:
        clear_all_run_state()


def clear_stored_file(
    session_state: dict[str, object],
    *,
    kind: str,
    clear_all_run_state: Optional[Callable[[], None]] = None,
) -> None:
    session_state[FILE_STATE_KEYS[kind]] = None
    for widget_key in UPLOADER_KEYS_BY_KIND.get(kind, ()):
        session_state.pop(widget_key, None)
    if clear_all_run_state is None:
        _clear_all_run_state(session_state)
    else:
        clear_all_run_state()


def render_file_input(
    *,
    session_state: dict[str, object],
    kind: str,
    label: str,
    file_types: list[str],
    uploader_key: str,
    clear_all_run_state: Optional[Callable[[], None]] = None,
    rerun: Optional[Callable[[], None]] = None,
) -> Optional[dict[str, object]]:
    rerun_fn = _rerun if rerun is None else rerun
    stored = get_stored_file(session_state, kind=kind)
    if stored is not None:
        filename = str(stored.get("name", ""))
        info_col, button_col = st.columns([5, 1])
        info_col.success(f"{label}: uppladdad ({filename})")
        if button_col.button("Byt fil", key=f"replace_{kind}_{uploader_key}"):
            clear_stored_file(
                session_state,
                kind=kind,
                clear_all_run_state=clear_all_run_state,
            )
            rerun_fn()
        return stored

    uploaded = st.file_uploader(
        label,
        type=file_types,
        accept_multiple_files=False,
        key=uploader_key,
    )
    if uploaded is not None:
        store_uploaded_file(
            session_state,
            kind=kind,
            uploaded_file=uploaded,
            clear_all_run_state=clear_all_run_state,
        )
        rerun_fn()
    return None
