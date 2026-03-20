from __future__ import annotations

from typing import Optional


def store_shared_sync_status(
    session_state: dict[str, object],
    *,
    level: str,
    message: Optional[str],
    profile_conflicts: tuple[str, ...] = (),
    source: Optional[str] = None,
) -> None:
    normalized_source = str(source).strip() if source is not None else ""
    session_state["shared_sync_status_level"] = level
    session_state["shared_sync_status_message"] = message
    session_state["shared_sync_profile_conflicts"] = profile_conflicts
    session_state["shared_sync_status_source"] = normalized_source or None
