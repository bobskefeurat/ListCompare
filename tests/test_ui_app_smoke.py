import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from streamlit.testing.v1 import AppTest

from listcompare.interfaces.ui.runtime_paths import DATA_DIR_ENV_VAR


class UiAppSmokeTests(unittest.TestCase):
    def test_app_runs_without_exceptions(self) -> None:
        data_dir = Path("tests") / "_tmp_app_smoke" / uuid4().hex
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            with patch.dict(os.environ, {DATA_DIR_ENV_VAR: str(data_dir)}, clear=False):
                app = AppTest.from_file("app.py")

                app.run(timeout=30)

                self.assertEqual(len(app.exception), 0, [str(exc) for exc in app.exception])
        finally:
            if data_dir.exists():
                shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
