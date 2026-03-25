from __future__ import annotations

from time import monotonic
from typing import Callable, Optional

from ..services.shared_sync import SHARED_SYNC_FILE_NAMES, SharedSyncStatus

AUTO_SHARED_SYNC_COOLDOWN_SECONDS = 10.0


def _normalized_auto_sync_targets(targets: tuple[str, ...]) -> tuple[str, ...]:
    normalized = [str(target) for target in targets if target in SHARED_SYNC_FILE_NAMES]
    return tuple(sorted(set(normalized), key=lambda value: value.casefold()))


def _auto_shared_sync_cache_key(targets: tuple[str, ...]) -> str:
    normalized_targets = _normalized_auto_sync_targets(targets)
    return "|".join(normalized_targets)


def maybe_run_auto_shared_sync(
    session_state: dict[str, object],
    *,
    sync_runner: Callable[..., SharedSyncStatus],
    targets: tuple[str, ...] = SHARED_SYNC_FILE_NAMES,
    min_interval_seconds: float = AUTO_SHARED_SYNC_COOLDOWN_SECONDS,
    now: Optional[float] = None,
) -> Optional[SharedSyncStatus]:
    normalized_targets = _normalized_auto_sync_targets(targets)
    cache_key = _auto_shared_sync_cache_key(normalized_targets)
    if cache_key == "":
        return sync_runner(targets=targets)

    cache = session_state.get("_auto_shared_sync_cache")
    if not isinstance(cache, dict):
        cache = {}
        session_state["_auto_shared_sync_cache"] = cache

    current_time = monotonic() if now is None else float(now)
    requested_target_set = set(normalized_targets)
    for cached_entry in cache.values():
        if not isinstance(cached_entry, dict):
            continue
        cached_run_at = cached_entry.get("run_at")
        cached_targets = cached_entry.get("targets")
        if not isinstance(cached_run_at, (int, float)) or not isinstance(cached_targets, tuple):
            continue
        cached_target_set = {str(target) for target in cached_targets}
        if not requested_target_set.issubset(cached_target_set):
            continue
        elapsed_seconds = current_time - float(cached_run_at)
        if elapsed_seconds < min_interval_seconds:
            return None

    status = sync_runner(targets=targets)
    cache[cache_key] = {
        "run_at": current_time,
        "targets": normalized_targets,
    }
    session_state["_auto_shared_sync_cache"] = cache
    return status


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
