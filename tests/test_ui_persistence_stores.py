import unittest

from listcompare.core.suppliers.profile import (
    SUPPLIER_HICORE_SKU_COLUMN,
)
from listcompare.interfaces.ui.persistence import (
    index_store,
    profile_store,
    settings_store,
)


class _InMemoryPath:
    def __init__(self) -> None:
        self._text: str | None = None

    def exists(self) -> bool:
        return self._text is not None

    def write_text(self, text: str, encoding: str = "utf-8") -> int:
        del encoding
        self._text = text
        return len(text)

    def read_text(self, encoding: str = "utf-8-sig") -> str:
        del encoding
        if self._text is None:
            raise FileNotFoundError
        return self._text

    @property
    def name(self) -> str:
        return "in-memory"


class UiPersistenceStoreTests(unittest.TestCase):
    def test_index_store_roundtrip_normalizes_names(self) -> None:
        path = _InMemoryPath()
        index_store.save_suppliers_to_index(path, [" Sony ", "sony", "Acme", ""])

        suppliers, err = index_store.load_suppliers_from_index(path)

        self.assertIsNone(err)
        self.assertEqual(suppliers, ["Acme", "Sony"])

    def test_index_store_reports_missing_index(self) -> None:
        path = _InMemoryPath()

        suppliers, err = index_store.load_brands_from_index(path)

        self.assertEqual(suppliers, [])
        self.assertIsNotNone(err)

    def test_settings_store_roundtrip_normalizes_excluded_brands(self) -> None:
        path = _InMemoryPath()
        save_err = settings_store.save_ui_settings(
            path,
            excluded_brands=[" Sony ", "sony", "Acme"],
        )
        self.assertIsNone(save_err)

        settings, load_err = settings_store.load_ui_settings(path)

        self.assertIsNone(load_err)
        self.assertEqual(settings["excluded_brands"], ["Acme", "Sony"])

    def test_profile_store_roundtrip(self) -> None:
        path = _InMemoryPath()
        save_err = profile_store.save_profiles(
            path,
            profiles={
                "EM Nordic": {
                    "target_to_source": {
                        SUPPLIER_HICORE_SKU_COLUMN: "SupplierSku",
                    },
                    "options": {
                        "strip_leading_zeros_from_sku": True,
                    },
                }
            },
        )
        self.assertIsNone(save_err)

        profiles, load_err = profile_store.load_profiles(path)

        self.assertIsNone(load_err)
        self.assertIn("EM Nordic", profiles)
        self.assertEqual(
            profiles["EM Nordic"]["target_to_source"][SUPPLIER_HICORE_SKU_COLUMN],
            "SupplierSku",
        )


if __name__ == "__main__":
    unittest.main()
