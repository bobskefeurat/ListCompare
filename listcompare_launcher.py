"""Launcher for running the bundled Streamlit UI as a desktop-style app."""

from __future__ import annotations

import asyncio
import os
import sys
import threading
import time
from collections.abc import Mapping
from pathlib import Path

# Keep the app package reachable from the frozen launcher so PyInstaller
# collects the UI modules that the bundled Streamlit script imports.
from listcompare.interfaces.ui.app import main as _bundled_app_main  # noqa: F401

AUTO_SHUTDOWN_ENV_VAR = "LISTCOMPARE_AUTO_SHUTDOWN_SECONDS"
DEFAULT_AUTO_SHUTDOWN_SECONDS = 15.0
RUNTIME_POLL_INTERVAL_SECONDS = 1.0
STREAMLIT_APP_FILE = "app.py"
OPEN_BROWSER_ENV_VAR = "LISTCOMPARE_OPEN_BROWSER"


def resource_root(*, frozen: bool | None = None, meipass: str | None = None) -> Path:
    """Return the directory that contains bundled runtime resources."""

    current_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if current_frozen:
        bundle_root = meipass
        if bundle_root is None:
            bundle_root = getattr(sys, "_MEIPASS", None)
        if bundle_root:
            return Path(bundle_root).resolve()
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def streamlit_app_path(*, root: Path | None = None) -> Path:
    """Resolve the bundled Streamlit entrypoint path."""

    base_root = resource_root() if root is None else root
    return (base_root / STREAMLIT_APP_FILE).resolve()


def open_browser_enabled(*, env: Mapping[str, str] | None = None) -> bool:
    """Return whether the launcher should open a browser window by default."""

    env_map = os.environ if env is None else env
    raw_value = str(env_map.get(OPEN_BROWSER_ENV_VAR, "")).strip().casefold()
    if raw_value in {"0", "false", "no", "off"}:
        return False
    return True


def auto_shutdown_seconds(
    *,
    env: Mapping[str, str] | None = None,
    open_browser: bool | None = None,
) -> float | None:
    """Resolve the idle shutdown timeout, or ``None`` when it is disabled."""

    env_map = os.environ if env is None else env
    raw_value = str(env_map.get(AUTO_SHUTDOWN_ENV_VAR, "")).strip()
    if raw_value != "":
        shutdown_seconds = float(raw_value)
        if shutdown_seconds <= 0:
            return None
        return shutdown_seconds

    open_browser_value = open_browser_enabled(env=env_map) if open_browser is None else open_browser
    if not open_browser_value:
        return None
    return DEFAULT_AUTO_SHUTDOWN_SECONDS


def runtime_flag_options(*, open_browser: bool | None = None) -> dict[str, object]:
    """Build Streamlit runtime flags for the packaged launcher environment."""

    open_browser_value = open_browser_enabled() if open_browser is None else open_browser
    return {
        "server_headless": not open_browser_value,
        "server_showEmailPrompt": False,
        "server_runOnSave": False,
        "server_fileWatcherType": "none",
        "browser_gatherUsageStats": False,
        "global_developmentMode": False,
    }


def script_args(argv: list[str] | None = None) -> list[str]:
    return list(sys.argv[1:] if argv is None else argv)


def _monitor_server_for_idle_shutdown(
    *,
    server: object,
    stop_after_seconds: float,
    poll_interval_seconds: float = RUNTIME_POLL_INTERVAL_SECONDS,
    sleep_fn=time.sleep,
    monotonic_fn=time.monotonic,
) -> None:
    idle_started_at: float | None = None

    while True:
        if getattr(server, "browser_is_connected"):
            idle_started_at = None
        else:
            now = monotonic_fn()
            if idle_started_at is None:
                idle_started_at = now
            elif now - idle_started_at >= stop_after_seconds:
                server.stop()
                return

        sleep_fn(poll_interval_seconds)


def start_server_shutdown_monitor(
    server: object,
    stop_after_seconds: float | None,
) -> threading.Thread | None:
    """Start a background thread that stops the server after idle timeout."""

    if stop_after_seconds is None:
        return None

    monitor_thread = threading.Thread(
        target=_monitor_server_for_idle_shutdown,
        kwargs={
            "server": server,
            "stop_after_seconds": stop_after_seconds,
        },
        name="ListCompareRuntimeShutdownMonitor",
        daemon=True,
    )
    monitor_thread.start()
    return monitor_thread


def main() -> None:
    """Bootstrap and run the packaged Streamlit server."""

    main_script_path = streamlit_app_path()
    if not main_script_path.exists():
        raise FileNotFoundError(
            f"Could not find bundled Streamlit app at {main_script_path}."
        )

    from streamlit import config as streamlit_config
    from streamlit.runtime.credentials import check_credentials
    from streamlit.web import bootstrap
    from streamlit.web.server import Server

    open_browser = open_browser_enabled()
    flag_options = runtime_flag_options(open_browser=open_browser)
    streamlit_config._main_script_path = str(main_script_path)
    bootstrap.load_config_options(flag_options=flag_options)
    check_credentials()

    bootstrap._fix_sys_path(str(main_script_path))
    bootstrap._fix_tornado_crash()
    bootstrap._fix_sys_argv(str(main_script_path), script_args())
    bootstrap._install_config_watchers(flag_options)

    if streamlit_config.get_option("server.useStarlette"):
        streamlit_config._server_mode = "starlette-managed"
    else:
        streamlit_config._server_mode = "tornado"

    server = Server(str(main_script_path), False)

    async def run_server() -> None:
        await server.start()
        bootstrap._on_server_start(server)
        bootstrap._set_up_signal_handler(server)
        start_server_shutdown_monitor(
            server,
            auto_shutdown_seconds(open_browser=open_browser),
        )
        await server.stopped

    running_in_event_loop = False
    try:
        asyncio.get_running_loop()
        running_in_event_loop = True
    except RuntimeError:
        pass

    if running_in_event_loop:
        asyncio.create_task(run_server(), name="listcompare.run_server")
        return

    bootstrap._maybe_install_uvloop(running_in_event_loop)
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
