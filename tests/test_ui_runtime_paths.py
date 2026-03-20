import unittest
from pathlib import Path

from listcompare.interfaces.ui import runtime_paths
from tests._support import cleanup_temp_path, make_temp_dir


class UiRuntimePathsTests(unittest.TestCase):
    def test_default_data_dir_uses_windows_local_app_data(self) -> None:
        data_dir = runtime_paths._default_data_dir(
            env={"LOCALAPPDATA": r"C:\Users\Info\AppData\Local"},
            os_name="nt",
            home_dir=Path(r"C:\Users\Info"),
        )

        self.assertEqual(
            data_dir,
            Path(r"C:\Users\Info\AppData\Local") / runtime_paths.APP_NAME,
        )

    def test_default_data_dir_prefers_override(self) -> None:
        data_dir = runtime_paths._default_data_dir(
            env={
                runtime_paths.DATA_DIR_ENV_VAR: "tests/runtime-data",
                "LOCALAPPDATA": r"C:\Ignored",
            },
            os_name="nt",
            home_dir=Path(r"C:\Users\Info"),
        )

        self.assertEqual(data_dir, Path("tests/runtime-data").resolve())

    def test_seed_source_roots_use_runtime_seed_subdirectory(self) -> None:
        temp_root = make_temp_dir("runtime-paths")
        try:
            project_root = temp_root / "project"
            data_dir = temp_root / "data"

            roots = runtime_paths._seed_source_roots(
                data_dir=data_dir,
                project_root=project_root,
            )

            self.assertEqual(
                roots,
                [(project_root / runtime_paths.RUNTIME_SEED_DIR_NAME).resolve()],
            )
        finally:
            if temp_root.exists():
                cleanup_temp_path(temp_root)

    def test_repository_runtime_seed_contains_all_persistent_files(self) -> None:
        seed_root = runtime_paths._seed_root(root=runtime_paths.PROJECT_ROOT)

        for file_name in runtime_paths.PERSISTENT_FILE_NAMES:
            self.assertTrue((seed_root / file_name).exists(), file_name)

    def test_initialize_runtime_storage_copies_missing_seed_files(self) -> None:
        temp_root = make_temp_dir("runtime-paths")
        try:
            source_root = temp_root / "seed"
            data_dir = temp_root / "data"
            source_root.mkdir(parents=True, exist_ok=True)
            data_dir.mkdir(parents=True, exist_ok=True)

            supplier_index_path = source_root / "supplier_index.txt"
            supplier_index_path.write_text("Acme\n", encoding="utf-8-sig")

            source_settings_path = source_root / "ui_settings.json"
            source_settings_path.write_text('{"excluded_brands":["Sony"]}\n', encoding="utf-8")

            data_settings_path = data_dir / "ui_settings.json"
            data_settings_path.write_text('{"excluded_brands":["Existing"]}\n', encoding="utf-8")

            runtime_paths._initialize_runtime_storage(
                data_dir=data_dir,
                source_roots=[source_root],
                file_names=("supplier_index.txt", "ui_settings.json", "brand_index.txt"),
            )

            self.assertEqual(
                (data_dir / "supplier_index.txt").read_text(encoding="utf-8-sig"),
                "Acme\n",
            )
            self.assertEqual(
                data_settings_path.read_text(encoding="utf-8"),
                '{"excluded_brands":["Existing"]}\n',
            )
            self.assertFalse((data_dir / "brand_index.txt").exists())
        finally:
            if temp_root.exists():
                cleanup_temp_path(temp_root)


if __name__ == "__main__":
    unittest.main()
