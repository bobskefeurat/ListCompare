import unittest
from pathlib import Path
import listcompare_launcher as launcher


class ListCompareLauncherTests(unittest.TestCase):
    def test_resource_root_uses_meipass_when_frozen(self) -> None:
        resource_root = launcher.resource_root(
            frozen=True,
            meipass=str(Path("tests").resolve()),
        )

        self.assertEqual(resource_root, Path("tests").resolve())

    def test_streamlit_app_path_uses_provided_root(self) -> None:
        root = Path("tests").resolve()

        self.assertEqual(
            launcher.streamlit_app_path(root=root),
            (root / launcher.STREAMLIT_APP_FILE).resolve(),
        )

    def test_open_browser_enabled_defaults_to_true(self) -> None:
        self.assertTrue(launcher.open_browser_enabled(env={}))

    def test_open_browser_enabled_accepts_false_like_values(self) -> None:
        self.assertFalse(
            launcher.open_browser_enabled(env={launcher.OPEN_BROWSER_ENV_VAR: "false"})
        )

    def test_runtime_flag_options_disable_prompt_and_watcher(self) -> None:
        flag_options = launcher.runtime_flag_options(open_browser=True)

        self.assertFalse(flag_options["server_headless"])
        self.assertFalse(flag_options["server_showEmailPrompt"])
        self.assertEqual(flag_options["server_fileWatcherType"], "none")
        self.assertFalse(flag_options["browser_gatherUsageStats"])

    def test_runtime_flag_options_support_headless_override(self) -> None:
        flag_options = launcher.runtime_flag_options(open_browser=False)

        self.assertTrue(flag_options["server_headless"])

    def test_auto_shutdown_seconds_defaults_for_browser_launch(self) -> None:
        self.assertEqual(
            launcher.auto_shutdown_seconds(env={}, open_browser=True),
            launcher.DEFAULT_AUTO_SHUTDOWN_SECONDS,
        )

    def test_auto_shutdown_seconds_is_disabled_for_headless_launch(self) -> None:
        self.assertIsNone(launcher.auto_shutdown_seconds(env={}, open_browser=False))

    def test_auto_shutdown_seconds_supports_env_override(self) -> None:
        self.assertEqual(
            launcher.auto_shutdown_seconds(
                env={launcher.AUTO_SHUTDOWN_ENV_VAR: "3.5"},
                open_browser=True,
            ),
            3.5,
        )

    def test_auto_shutdown_seconds_zero_disables_watchdog(self) -> None:
        self.assertIsNone(
            launcher.auto_shutdown_seconds(
                env={launcher.AUTO_SHUTDOWN_ENV_VAR: "0"},
                open_browser=True,
            )
        )

    def test_monitor_server_for_idle_shutdown_stops_server(self) -> None:
        class FakeServer:
            def __init__(self) -> None:
                self._connections = iter(
                    [
                        False,
                        False,
                    ]
                )
                self.stop_calls = 0

            @property
            def browser_is_connected(self) -> bool:
                return next(self._connections)

            def stop(self) -> None:
                self.stop_calls += 1

        fake_server = FakeServer()
        monotonic_values = iter([0.0, 20.0])

        launcher._monitor_server_for_idle_shutdown(
            server=fake_server,
            stop_after_seconds=15.0,
            poll_interval_seconds=0.0,
            sleep_fn=lambda _: None,
            monotonic_fn=lambda: next(monotonic_values),
        )

        self.assertEqual(fake_server.stop_calls, 1)


if __name__ == "__main__":
    unittest.main()
