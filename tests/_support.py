from __future__ import annotations

import shutil
import importlib
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_TEMP_ROOT = REPO_ROOT / ".tmp_tests"


def cleanup_temp_path(path: Path) -> None:
    if not path.exists():
        return

    shutil.rmtree(path)
    if path.exists():
        raise AssertionError(f"Temporary test path still exists after cleanup: {path}")


def make_temp_dir(prefix: str) -> Path:
    normalized_prefix = prefix.replace("_", "-").replace(" ", "-")
    temp_dir = TEST_TEMP_ROOT / normalized_prefix / uuid4().hex
    temp_dir.mkdir(parents=True, exist_ok=False)
    return temp_dir


class RepoTemporaryDirectory:
    def __init__(self, prefix: str) -> None:
        self.path = make_temp_dir(prefix)
        self.name = str(self.path)
        self._closed = False

    def cleanup(self) -> None:
        if self._closed:
            return
        cleanup_temp_path(self.path)
        self._closed = True

    def __enter__(self) -> str:
        return self.name

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()


def import_streamlit_apptest_with_repo_tempdir():
    from unittest.mock import patch

    for module_name in ("streamlit.testing.v1", "streamlit.testing.v1.app_test"):
        sys.modules.pop(module_name, None)

    created_temp_dirs: list[RepoTemporaryDirectory] = []

    def _temporary_directory_factory(*args, **kwargs):
        temp_dir = RepoTemporaryDirectory("streamlit-apptest")
        created_temp_dirs.append(temp_dir)
        return temp_dir

    with patch.object(tempfile, "TemporaryDirectory", _temporary_directory_factory):
        app_test_module = importlib.import_module("streamlit.testing.v1.app_test")

    return app_test_module.AppTest, app_test_module, created_temp_dirs
