import os
import shutil
import unittest
from pathlib import Path

import compile_python_sources

from tests._support import cleanup_temp_path, make_temp_dir


class CompilePythonSourcesTests(unittest.TestCase):
    def test_should_skip_dirname_filters_temp_and_generated_roots(self) -> None:
        self.assertTrue(compile_python_sources.should_skip_dirname("tmpabc"))
        self.assertTrue(compile_python_sources.should_skip_dirname("_tmp_cache"))
        self.assertTrue(compile_python_sources.should_skip_dirname("__pycache__"))
        self.assertFalse(compile_python_sources.should_skip_dirname("listcompare"))

    def test_iter_python_files_skips_temp_named_directories(self) -> None:
        temp_root = make_temp_dir("compile-python-sources")
        try:
            root = temp_root / "scan-root"
            keep_dir = root / "tests"
            skip_dir = keep_dir / "tmp_should_skip"
            nested_skip_dir = keep_dir / "_tmp_nested"
            keep_dir.mkdir(parents=True, exist_ok=True)
            skip_dir.mkdir(parents=True, exist_ok=True)
            nested_skip_dir.mkdir(parents=True, exist_ok=True)

            keep_file = keep_dir / "test_keep.py"
            skipped_file = skip_dir / "test_skip.py"
            nested_skipped_file = nested_skip_dir / "test_nested_skip.py"
            keep_file.write_text("x = 1\n", encoding="utf-8")
            skipped_file.write_text("y = 2\n", encoding="utf-8")
            nested_skipped_file.write_text("z = 3\n", encoding="utf-8")

            collected_paths: list[Path] = []
            for current_root, dirnames, filenames in os.walk(root, topdown=True):
                dirnames[:] = sorted(
                    dirname
                    for dirname in dirnames
                    if not compile_python_sources.should_skip_dirname(dirname)
                )
                for filename in filenames:
                    if filename.endswith(".py"):
                        collected_paths.append(Path(current_root) / filename)
        finally:
            if temp_root.exists():
                cleanup_temp_path(temp_root)

        self.assertEqual(collected_paths, [keep_file])

    def test_compile_python_files_reports_syntax_errors(self) -> None:
        temp_root = make_temp_dir("compile-python-sources")
        try:
            good_file = temp_root / "good.py"
            bad_file = temp_root / "bad.py"
            good_file.write_text("value = 1\n", encoding="utf-8")
            bad_file.write_text("if True print('broken')\n", encoding="utf-8")

            errors = compile_python_sources.compile_python_files([good_file, bad_file])
        finally:
            if temp_root.exists():
                cleanup_temp_path(temp_root)

        self.assertEqual(len(errors), 1)
        self.assertIn("bad.py", errors[0])
        self.assertIn("SyntaxError", errors[0])


if __name__ == "__main__":
    unittest.main()
