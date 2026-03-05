from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import streamlit as st

ProgressUpdate = Callable[[float, str], None]
ProgressClear = Callable[[], None]


def with_one_based_index(df: pd.DataFrame) -> pd.DataFrame:
    display_df = df.copy()
    display_df.index = range(1, len(display_df) + 1)
    return display_df


def build_progress_updater(*, label: str) -> tuple[ProgressUpdate, ProgressClear]:
    status_placeholder = st.empty()
    progress_placeholder = st.empty()
    progress_bar = progress_placeholder.progress(0)

    def _update(progress: float, message: str) -> None:
        clamped = max(0.0, min(1.0, float(progress)))
        percent = int(round(clamped * 100))
        status_text = str(message).strip()
        if status_text != "":
            status_placeholder.caption(f"{label}: {status_text} ({percent}%)")
        else:
            status_placeholder.caption(f"{label}: {percent}%")
        progress_bar.progress(percent)

    def _clear() -> None:
        status_placeholder.empty()
        progress_placeholder.empty()

    return _update, _clear
