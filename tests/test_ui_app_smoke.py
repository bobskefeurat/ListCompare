import unittest

from streamlit.testing.v1 import AppTest


class UiAppSmokeTests(unittest.TestCase):
    def test_app_runs_without_exceptions(self) -> None:
        app = AppTest.from_file("app.py")

        app.run(timeout=30)

        self.assertEqual(len(app.exception), 0, [str(exc) for exc in app.exception])


if __name__ == "__main__":
    unittest.main()
