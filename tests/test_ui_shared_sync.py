import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from listcompare.core.suppliers.profile import SUPPLIER_HICORE_SKU_COLUMN
from listcompare.interfaces.ui.persistence import index_store, profile_store
from listcompare.interfaces.ui.services import shared_sync


def _profile_payload(source_column: str) -> dict[str, dict[str, object]]:
    return {
        "EM Nordic": {
            "target_to_source": {
                SUPPLIER_HICORE_SKU_COLUMN: source_column,
            },
            "options": {
                "strip_leading_zeros_from_sku": False,
            },
        }
    }


class _SharedSyncPaths:
    def __init__(self, temp_root: Path) -> None:
        self.temp_root = temp_root
        self.data_dir = temp_root / "data"
        self.shared_dir = temp_root / "shared"
        self.base_dir = temp_root / "base"
        self.config_path = temp_root / "shared_sync_config.json"
        self.local_supplier_index_path = self.data_dir / shared_sync.SUPPLIER_INDEX_FILE_NAME
        self.local_brand_index_path = self.data_dir / shared_sync.BRAND_INDEX_FILE_NAME
        self.local_profiles_path = self.data_dir / shared_sync.PROFILES_FILE_NAME
        self.shared_supplier_index_path = self.shared_dir / shared_sync.SUPPLIER_INDEX_FILE_NAME
        self.shared_brand_index_path = self.shared_dir / shared_sync.BRAND_INDEX_FILE_NAME
        self.shared_profiles_path = self.shared_dir / shared_sync.PROFILES_FILE_NAME
        self.base_profiles_path = self.base_dir / shared_sync.PROFILES_FILE_NAME

    def __enter__(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.shared_dir.mkdir(parents=True, exist_ok=True)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._old_values = {
            "_shared_sync_config_path": shared_sync._shared_sync_config_path,
            "_shared_sync_base_dir": shared_sync._shared_sync_base_dir,
            "_supplier_index_path": shared_sync._supplier_index_path,
            "_brand_index_path": shared_sync._brand_index_path,
            "_supplier_transform_profiles_path": shared_sync._supplier_transform_profiles_path,
        }
        shared_sync._shared_sync_config_path = lambda: self.config_path
        shared_sync._shared_sync_base_dir = lambda: self.base_dir
        shared_sync._supplier_index_path = lambda: self.local_supplier_index_path
        shared_sync._brand_index_path = lambda: self.local_brand_index_path
        shared_sync._supplier_transform_profiles_path = lambda: self.local_profiles_path
        return self

    def __exit__(self, exc_type, exc, tb):
        for name, value in self._old_values.items():
            setattr(shared_sync, name, value)


class SharedSyncTests(unittest.TestCase):
    def test_candidate_search_includes_configured_shared_folder(self) -> None:
        temp_root = Path("tests") / "_tmp_shared_sync" / uuid4().hex
        try:
            with _SharedSyncPaths(temp_root) as paths:
                old_loader = shared_sync.load_configured_shared_folder
                shared_sync.load_configured_shared_folder = lambda: (str(paths.shared_dir), None)
                try:
                    candidates = shared_sync.find_shared_sync_folder_candidates()
                finally:
                    shared_sync.load_configured_shared_folder = old_loader
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root, ignore_errors=True)

        self.assertIn(str((temp_root / "shared").resolve()), candidates)

    def test_sync_auto_configures_single_detected_shared_folder(self) -> None:
        temp_root = Path("tests") / "_tmp_shared_sync" / uuid4().hex
        try:
            with _SharedSyncPaths(temp_root) as paths:
                old_finder = shared_sync.find_shared_sync_folder_candidates
                shared_sync.find_shared_sync_folder_candidates = (
                    lambda *, folder_name="ListCompareShared": [str(paths.shared_dir)]
                )
                try:
                    index_store.save_suppliers_to_index(paths.local_supplier_index_path, ["EM Nordic"])

                    status = shared_sync.sync_shared_files(
                        targets=(shared_sync.SUPPLIER_INDEX_FILE_NAME,)
                    )
                    configured_folder, config_error = shared_sync.load_configured_shared_folder()
                    shared_suppliers, suppliers_error = index_store.load_suppliers_from_index(
                        paths.shared_supplier_index_path
                    )
                finally:
                    shared_sync.find_shared_sync_folder_candidates = old_finder
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root, ignore_errors=True)

        self.assertEqual(status.level, "success")
        self.assertIn("aktiverade delad synkmapp automatiskt", status.message)
        self.assertIsNone(config_error)
        self.assertEqual(configured_folder, str(paths.shared_dir))
        self.assertIsNone(suppliers_error)
        self.assertEqual(shared_suppliers, ["EM Nordic"])

    def test_sync_disabled_without_configured_folder(self) -> None:
        temp_root = Path("tests") / "_tmp_shared_sync" / uuid4().hex
        try:
            with _SharedSyncPaths(temp_root):
                old_finder = shared_sync.find_shared_sync_folder_candidates
                try:
                    shared_sync.find_shared_sync_folder_candidates = lambda folder_name="": []
                    status = shared_sync.sync_shared_files()
                finally:
                    shared_sync.find_shared_sync_folder_candidates = old_finder
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root, ignore_errors=True)

        self.assertEqual(status.level, "disabled")
        self.assertIn("Ingen delad synkmapp vald", status.message)

    def test_first_sync_seeds_shared_files_from_local_data(self) -> None:
        temp_root = Path("tests") / "_tmp_shared_sync" / uuid4().hex
        try:
            with _SharedSyncPaths(temp_root) as paths:
                index_store.save_suppliers_to_index(paths.local_supplier_index_path, ["EM Nordic"])
                index_store.save_brands_to_index(paths.local_brand_index_path, ["Sony"])
                profile_store.save_profiles(
                    paths.local_profiles_path,
                    profiles=_profile_payload("SupplierSku"),
                )
                shared_sync.save_configured_shared_folder(str(paths.shared_dir))

                status = shared_sync.sync_shared_files()

                shared_suppliers, suppliers_error = index_store.load_suppliers_from_index(
                    paths.shared_supplier_index_path
                )
                shared_brands, brands_error = index_store.load_brands_from_index(
                    paths.shared_brand_index_path
                )
                shared_profiles, profiles_error = profile_store.load_profiles(paths.shared_profiles_path)
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root, ignore_errors=True)

        self.assertEqual(status.level, "success")
        self.assertIsNone(suppliers_error)
        self.assertIsNone(brands_error)
        self.assertIsNone(profiles_error)
        self.assertEqual(shared_suppliers, ["EM Nordic"])
        self.assertEqual(shared_brands, ["Sony"])
        self.assertEqual(
            shared_profiles["EM Nordic"]["target_to_source"][SUPPLIER_HICORE_SKU_COLUMN],
            "SupplierSku",
        )

    def test_sync_merges_supplier_index_names_from_local_and_shared(self) -> None:
        temp_root = Path("tests") / "_tmp_shared_sync" / uuid4().hex
        try:
            with _SharedSyncPaths(temp_root) as paths:
                index_store.save_suppliers_to_index(paths.local_supplier_index_path, ["EM Nordic"])
                index_store.save_suppliers_to_index(paths.shared_supplier_index_path, ["Yamaha"])
                shared_sync.save_configured_shared_folder(str(paths.shared_dir))

                status = shared_sync.sync_shared_files(targets=(shared_sync.SUPPLIER_INDEX_FILE_NAME,))
                local_suppliers, local_error = index_store.load_suppliers_from_index(
                    paths.local_supplier_index_path
                )
                shared_suppliers, shared_error = index_store.load_suppliers_from_index(
                    paths.shared_supplier_index_path
                )
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root, ignore_errors=True)

        self.assertEqual(status.level, "success")
        self.assertIsNone(local_error)
        self.assertIsNone(shared_error)
        self.assertEqual(local_suppliers, ["EM Nordic", "Yamaha"])
        self.assertEqual(shared_suppliers, ["EM Nordic", "Yamaha"])

    def test_sync_pulls_updated_shared_profiles_when_local_matches_base(self) -> None:
        temp_root = Path("tests") / "_tmp_shared_sync" / uuid4().hex
        try:
            with _SharedSyncPaths(temp_root) as paths:
                profile_store.save_profiles(
                    paths.local_profiles_path,
                    profiles=_profile_payload("SupplierSkuOld"),
                )
                shared_sync.save_configured_shared_folder(str(paths.shared_dir))
                shared_sync.sync_shared_files(targets=(shared_sync.PROFILES_FILE_NAME,))

                profile_store.save_profiles(
                    paths.shared_profiles_path,
                    profiles=_profile_payload("SupplierSkuNew"),
                )

                status = shared_sync.sync_shared_files(targets=(shared_sync.PROFILES_FILE_NAME,))
                local_profiles, local_error = profile_store.load_profiles(paths.local_profiles_path)
                base_profiles, base_error = profile_store.load_profiles(paths.base_profiles_path)
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root, ignore_errors=True)

        self.assertEqual(status.level, "success")
        self.assertIsNone(local_error)
        self.assertIsNone(base_error)
        self.assertEqual(
            local_profiles["EM Nordic"]["target_to_source"][SUPPLIER_HICORE_SKU_COLUMN],
            "SupplierSkuNew",
        )
        self.assertEqual(
            base_profiles["EM Nordic"]["target_to_source"][SUPPLIER_HICORE_SKU_COLUMN],
            "SupplierSkuNew",
        )

    def test_sync_warns_when_same_profile_changes_on_both_sides(self) -> None:
        temp_root = Path("tests") / "_tmp_shared_sync" / uuid4().hex
        try:
            with _SharedSyncPaths(temp_root) as paths:
                profile_store.save_profiles(
                    paths.base_profiles_path,
                    profiles=_profile_payload("SupplierSkuBase"),
                )
                profile_store.save_profiles(
                    paths.local_profiles_path,
                    profiles=_profile_payload("SupplierSkuLocal"),
                )
                profile_store.save_profiles(
                    paths.shared_profiles_path,
                    profiles=_profile_payload("SupplierSkuShared"),
                )
                shared_sync.save_configured_shared_folder(str(paths.shared_dir))

                status = shared_sync.sync_shared_files(targets=(shared_sync.PROFILES_FILE_NAME,))
                local_profiles, local_error = profile_store.load_profiles(paths.local_profiles_path)
                shared_profiles, shared_error = profile_store.load_profiles(paths.shared_profiles_path)
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root, ignore_errors=True)

        self.assertEqual(status.level, "warning")
        self.assertEqual(status.profile_conflicts, ("EM Nordic",))
        self.assertIsNone(local_error)
        self.assertIsNone(shared_error)
        self.assertEqual(
            local_profiles["EM Nordic"]["target_to_source"][SUPPLIER_HICORE_SKU_COLUMN],
            "SupplierSkuLocal",
        )
        self.assertEqual(
            shared_profiles["EM Nordic"]["target_to_source"][SUPPLIER_HICORE_SKU_COLUMN],
            "SupplierSkuShared",
        )


if __name__ == "__main__":
    unittest.main()
