import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from listcompare.interfaces.ui.runtime_paths import DATA_DIR_ENV_VAR
from tests._support import (
    TEST_TEMP_ROOT,
    cleanup_temp_path,
    import_streamlit_apptest_with_repo_tempdir,
    make_temp_dir,
)


class UiAppSmokeTests(unittest.TestCase):
    def test_app_runs_without_exceptions(self) -> None:
        data_dir = make_temp_dir("app-smoke")
        app_test_module = None
        app_test_temp_dirs = []
        try:
            with patch.dict(os.environ, {DATA_DIR_ENV_VAR: str(data_dir)}, clear=False):
                AppTest, app_test_module, app_test_temp_dirs = (
                    import_streamlit_apptest_with_repo_tempdir()
                )
                app = AppTest.from_file("app.py")

                app.run(timeout=30)

                self.assertEqual(len(app.exception), 0, [str(exc) for exc in app.exception])
                self.assertTrue(Path(app_test_module.TMP_DIR.name).is_relative_to(TEST_TEMP_ROOT))
                self.assertEqual(
                    json.loads((data_dir / "ui_settings.json").read_text(encoding="utf-8")),
                    {"excluded_brands": []},
                )
                self.assertEqual(
                    json.loads(
                        (data_dir / "supplier_transform_profiles.json").read_text(
                            encoding="utf-8"
                        )
                    ),
                    {"profiles": {}},
                )
                self.assertEqual(
                    (data_dir / "supplier_index.txt").read_text(encoding="utf-8-sig").strip(),
                    "",
                )
                self.assertEqual(
                    (data_dir / "brand_index.txt").read_text(encoding="utf-8-sig").strip(),
                    "",
                )
        finally:
            for temp_dir in reversed(app_test_temp_dirs):
                temp_dir.cleanup()
            if data_dir.exists():
                cleanup_temp_path(data_dir)


if __name__ == "__main__":
    unittest.main()
