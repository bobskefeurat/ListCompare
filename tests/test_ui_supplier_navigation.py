import unittest
from unittest.mock import Mock

from listcompare.interfaces.ui.common import (
    SUPPLIER_PAGE_VIEW_TRANSFORM,
    SUPPLIER_PROFILE_MODE_EDITOR,
)
from listcompare.interfaces.ui.session.navigation import request_supplier_profile_editor
from listcompare.interfaces.ui.session.supplier_selection import (
    sync_selected_supplier_between_views,
    sync_supplier_selection_session_state,
)


class SupplierNavigationUiTests(unittest.TestCase):
    def test_request_supplier_profile_editor_sets_requests_and_reruns(self) -> None:
        session_state: dict[str, object] = {}
        rerun_mock = Mock()

        request_supplier_profile_editor(
            session_state,
            "  EM Nordic  ",
            rerun_fn=rerun_mock,
        )

        self.assertEqual(
            session_state["supplier_page_view_request"],
            SUPPLIER_PAGE_VIEW_TRANSFORM,
        )
        self.assertEqual(
            session_state["supplier_profiles_mode_request"],
            SUPPLIER_PROFILE_MODE_EDITOR,
        )
        self.assertEqual(
            session_state["supplier_profiles_supplier_request"],
            "EM Nordic",
        )
        rerun_mock.assert_called_once()

    def test_request_supplier_profile_editor_ignores_blank_supplier(self) -> None:
        session_state: dict[str, object] = {
            "supplier_page_view_request": None,
            "supplier_profiles_mode_request": None,
            "supplier_profiles_supplier_request": None,
        }
        rerun_mock = Mock()

        request_supplier_profile_editor(
            session_state,
            "   ",
            rerun_fn=rerun_mock,
        )

        self.assertIsNone(session_state["supplier_page_view_request"])
        self.assertIsNone(session_state["supplier_profiles_mode_request"])
        self.assertIsNone(session_state["supplier_profiles_supplier_request"])
        rerun_mock.assert_not_called()

    def test_sync_supplier_selection_session_state_normalizes_and_syncs(self) -> None:
        session_state: dict[str, object] = {
            "supplier_internal_name": "  Sony  ",
            "supplier_transform_internal_name": "Old Name",
            "_last_supplier_internal_name": None,
        }

        sync_supplier_selection_session_state(session_state, ["Sony", "Acme"])

        self.assertEqual(session_state["supplier_internal_name"], "Sony")
        self.assertEqual(session_state["supplier_transform_internal_name"], "Sony")
        self.assertEqual(session_state["_last_supplier_internal_name"], "Sony")

    def test_sync_supplier_selection_session_state_clears_invalid_value(self) -> None:
        session_state: dict[str, object] = {
            "supplier_internal_name": "Unknown Supplier",
            "supplier_transform_internal_name": "Sony",
            "_last_supplier_internal_name": "Sony",
        }

        sync_supplier_selection_session_state(session_state, ["Sony", "Acme"])

        self.assertIsNone(session_state["supplier_internal_name"])
        self.assertIsNone(session_state["supplier_transform_internal_name"])
        self.assertIsNone(session_state["_last_supplier_internal_name"])

    def test_sync_selected_supplier_between_views_updates_target_key(self) -> None:
        session_state: dict[str, object] = {
            "supplier_transform_internal_name": None,
            "_last_supplier_internal_name": None,
        }

        sync_selected_supplier_between_views(
            session_state,
            "  Acme  ",
            ["Sony", "Acme"],
            target_key="supplier_transform_internal_name",
        )

        self.assertEqual(session_state["supplier_transform_internal_name"], "Acme")
        self.assertEqual(session_state["_last_supplier_internal_name"], "Acme")


if __name__ == "__main__":
    unittest.main()
