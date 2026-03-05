import unittest
from unittest.mock import Mock, patch

from listcompare.interfaces.ui import state as ui_state
from listcompare.interfaces.ui.common import (
    SUPPLIER_PAGE_VIEW_TRANSFORM,
    SUPPLIER_PROFILE_MODE_EDITOR,
)


class _FakeStreamlit:
    def __init__(self, session_state: dict[str, object] | None = None) -> None:
        self.session_state: dict[str, object] = session_state or {}


class SupplierNavigationUiTests(unittest.TestCase):
    def test_request_supplier_profile_editor_sets_requests_and_reruns(self) -> None:
        fake_st = _FakeStreamlit()
        rerun_mock = Mock()

        with patch.object(ui_state, "st", fake_st), patch.object(ui_state, "_rerun", rerun_mock):
            ui_state._request_supplier_profile_editor("  EM Nordic  ")

        self.assertEqual(
            fake_st.session_state["supplier_page_view_request"],
            SUPPLIER_PAGE_VIEW_TRANSFORM,
        )
        self.assertEqual(
            fake_st.session_state["supplier_profiles_mode_request"],
            SUPPLIER_PROFILE_MODE_EDITOR,
        )
        self.assertEqual(
            fake_st.session_state["supplier_profiles_supplier_request"],
            "EM Nordic",
        )
        rerun_mock.assert_called_once()

    def test_request_supplier_profile_editor_ignores_blank_supplier(self) -> None:
        fake_st = _FakeStreamlit(
            {
                "supplier_page_view_request": None,
                "supplier_profiles_mode_request": None,
                "supplier_profiles_supplier_request": None,
            }
        )
        rerun_mock = Mock()

        with patch.object(ui_state, "st", fake_st), patch.object(ui_state, "_rerun", rerun_mock):
            ui_state._request_supplier_profile_editor("   ")

        self.assertIsNone(fake_st.session_state["supplier_page_view_request"])
        self.assertIsNone(fake_st.session_state["supplier_profiles_mode_request"])
        self.assertIsNone(fake_st.session_state["supplier_profiles_supplier_request"])
        rerun_mock.assert_not_called()

    def test_sync_supplier_selection_session_state_normalizes_and_syncs(self) -> None:
        fake_st = _FakeStreamlit(
            {
                "supplier_internal_name": "  Sony  ",
                "supplier_transform_internal_name": "Old Name",
                "_last_supplier_internal_name": None,
            }
        )

        with patch.object(ui_state, "st", fake_st):
            ui_state._sync_supplier_selection_session_state(["Sony", "Acme"])

        self.assertEqual(fake_st.session_state["supplier_internal_name"], "Sony")
        self.assertEqual(fake_st.session_state["supplier_transform_internal_name"], "Sony")
        self.assertEqual(fake_st.session_state["_last_supplier_internal_name"], "Sony")

    def test_sync_supplier_selection_session_state_clears_invalid_value(self) -> None:
        fake_st = _FakeStreamlit(
            {
                "supplier_internal_name": "Unknown Supplier",
                "supplier_transform_internal_name": "Sony",
                "_last_supplier_internal_name": "Sony",
            }
        )

        with patch.object(ui_state, "st", fake_st):
            ui_state._sync_supplier_selection_session_state(["Sony", "Acme"])

        self.assertIsNone(fake_st.session_state["supplier_internal_name"])
        self.assertIsNone(fake_st.session_state["supplier_transform_internal_name"])
        self.assertIsNone(fake_st.session_state["_last_supplier_internal_name"])

    def test_sync_selected_supplier_between_views_updates_target_key(self) -> None:
        fake_st = _FakeStreamlit(
            {
                "supplier_transform_internal_name": None,
                "_last_supplier_internal_name": None,
            }
        )

        with patch.object(ui_state, "st", fake_st):
            ui_state._sync_selected_supplier_between_views(
                "  Acme  ",
                ["Sony", "Acme"],
                target_key="supplier_transform_internal_name",
            )

        self.assertEqual(fake_st.session_state["supplier_transform_internal_name"], "Acme")
        self.assertEqual(fake_st.session_state["_last_supplier_internal_name"], "Acme")


if __name__ == "__main__":
    unittest.main()
