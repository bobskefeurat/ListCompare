import unittest
from unittest.mock import Mock, patch

from listcompare.interfaces.ui.common import (
    SUPPLIER_PAGE_VIEW_COMPARE,
    SUPPLIER_PAGE_VIEW_TRANSFORM,
)
from listcompare.interfaces.ui.pages import supplier
from listcompare.interfaces.ui.services.shared_sync import SharedSyncStatus


class SupplierPageTests(unittest.TestCase):
    def test_syncs_profiles_when_entering_transform_view(self) -> None:
        session_state: dict[str, object] = {
            "supplier_page_view_last_rendered": SUPPLIER_PAGE_VIEW_COMPARE,
            "supplier_transform_profiles": {},
            "supplier_transform_profiles_load_error": None,
        }
        sync_mock = Mock(
            return_value=SharedSyncStatus(
                level="success",
                message="Synkad",
                shared_folder=r"G:\Min enhet\ListCompareShared",
            )
        )

        with patch.object(supplier, "_sync_shared_files", sync_mock), patch.object(
            supplier._profile_store,
            "load_profiles",
            return_value=({"EM Nordic": {"target_to_source": {}}}, None),
        ), patch.object(
            supplier,
            "_load_suppliers_from_index",
            return_value=(["EM Nordic", "Yamaha"], None),
        ):
            (
                supplier_options,
                supplier_index_error,
                warning_message,
            ) = supplier._sync_supplier_profiles_on_view_entry(
                session_state,
                selected_view=SUPPLIER_PAGE_VIEW_TRANSFORM,
                supplier_options=["EM Nordic"],
                supplier_index_error="gammalt fel",
            )

        sync_mock.assert_called_once_with(
            targets=(supplier._SUPPLIER_INDEX_FILE_NAME, supplier._PROFILES_FILE_NAME)
        )
        self.assertEqual(supplier_options, ["EM Nordic", "Yamaha"])
        self.assertIsNone(supplier_index_error)
        self.assertIsNone(warning_message)
        self.assertEqual(session_state["shared_sync_status_level"], "success")
        self.assertEqual(session_state["shared_sync_status_message"], "Synkad")
        self.assertEqual(
            session_state["supplier_transform_profiles"],
            {"EM Nordic": {"target_to_source": {}}},
        )

    def test_does_not_sync_when_transform_view_is_already_open(self) -> None:
        session_state: dict[str, object] = {
            "supplier_page_view_last_rendered": SUPPLIER_PAGE_VIEW_TRANSFORM,
        }
        sync_mock = Mock()

        with patch.object(supplier, "_sync_shared_files", sync_mock):
            (
                supplier_options,
                supplier_index_error,
                warning_message,
            ) = supplier._sync_supplier_profiles_on_view_entry(
                session_state,
                selected_view=SUPPLIER_PAGE_VIEW_TRANSFORM,
                supplier_options=["EM Nordic"],
                supplier_index_error=None,
            )

        sync_mock.assert_not_called()
        self.assertEqual(supplier_options, ["EM Nordic"])
        self.assertIsNone(supplier_index_error)
        self.assertIsNone(warning_message)

    def test_does_not_sync_when_compare_view_is_selected(self) -> None:
        session_state: dict[str, object] = {
            "supplier_page_view_last_rendered": SUPPLIER_PAGE_VIEW_COMPARE,
        }
        sync_mock = Mock()

        with patch.object(supplier, "_sync_shared_files", sync_mock):
            (
                supplier_options,
                supplier_index_error,
                warning_message,
            ) = supplier._sync_supplier_profiles_on_view_entry(
                session_state,
                selected_view=SUPPLIER_PAGE_VIEW_COMPARE,
                supplier_options=["EM Nordic"],
                supplier_index_error=None,
            )

        sync_mock.assert_not_called()
        self.assertEqual(supplier_options, ["EM Nordic"])
        self.assertIsNone(supplier_index_error)
        self.assertIsNone(warning_message)


if __name__ == "__main__":
    unittest.main()
