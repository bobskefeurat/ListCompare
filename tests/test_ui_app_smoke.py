import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from listcompare.interfaces.ui.runtime_paths import DATA_DIR_ENV_VAR


class UiAppSmokeTests(unittest.TestCase):
    def test_app_runs_without_exceptions(self) -> None:
        test_root = Path("tests").resolve()
        with TemporaryDirectory(dir=test_root) as data_dir:
            with patch.dict(os.environ, {DATA_DIR_ENV_VAR: data_dir}, clear=False):
                app = AppTest.from_file("app.py")

                app.run(timeout=30)

                self.assertEqual(len(app.exception), 0, [str(exc) for exc in app.exception])


if __name__ == "__main__":
    unittest.main()
