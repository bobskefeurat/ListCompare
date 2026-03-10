import unittest

from listcompare.interfaces.ui.common import (
    SUPPLIER_PAGE_VIEW_COMPARE,
    SUPPLIER_PAGE_VIEW_TRANSFORM,
    SUPPLIER_PROFILE_MODE_EDITOR,
    SUPPLIER_PROFILE_MODE_OVERVIEW,
)
from listcompare.interfaces.ui.session.supplier_page_state import (
    apply_requested_supplier_page_state,
)


class SupplierPageStateTests(unittest.TestCase):
    def test_apply_requested_state_sets_view_mode_and_supplier(self) -> None:
        session_state: dict[str, object] = {
            "supplier_page_view_request": SUPPLIER_PAGE_VIEW_TRANSFORM,
            "supplier_profiles_mode_request": SUPPLIER_PROFILE_MODE_EDITOR,
            "supplier_profiles_supplier_request": "Acme",
            "supplier_page_view": SUPPLIER_PAGE_VIEW_COMPARE,
            "supplier_page_view_last_rendered": SUPPLIER_PAGE_VIEW_COMPARE,
            "supplier_profiles_mode": SUPPLIER_PROFILE_MODE_OVERVIEW,
        }

        apply_requested_supplier_page_state(
            session_state,
            supplier_options=["Sony", "Acme"],
        )

        self.assertEqual(session_state["supplier_page_view"], SUPPLIER_PAGE_VIEW_TRANSFORM)
        self.assertEqual(session_state["supplier_profiles_mode"], SUPPLIER_PROFILE_MODE_EDITOR)
        self.assertEqual(session_state["supplier_profiles_active_supplier"], "Acme")
        self.assertEqual(session_state["supplier_internal_name"], "Acme")
        self.assertEqual(session_state["supplier_transform_internal_name"], "Acme")
        self.assertIsNone(session_state["supplier_page_view_request"])
        self.assertIsNone(session_state["supplier_profiles_mode_request"])
        self.assertIsNone(session_state["supplier_profiles_supplier_request"])

    def test_apply_requested_state_falls_back_to_compare_for_invalid_view(self) -> None:
        session_state: dict[str, object] = {
            "supplier_page_view_request": None,
            "supplier_profiles_mode_request": None,
            "supplier_profiles_supplier_request": None,
            "supplier_page_view": "invalid",
            "supplier_page_view_last_rendered": SUPPLIER_PAGE_VIEW_COMPARE,
            "supplier_profiles_mode": SUPPLIER_PROFILE_MODE_OVERVIEW,
        }

        apply_requested_supplier_page_state(
            session_state,
            supplier_options=["Sony", "Acme"],
        )

        self.assertEqual(session_state["supplier_page_view"], SUPPLIER_PAGE_VIEW_COMPARE)

    def test_apply_requested_state_sets_overview_mode_when_switching_to_transform(self) -> None:
        session_state: dict[str, object] = {
            "supplier_page_view_request": SUPPLIER_PAGE_VIEW_TRANSFORM,
            "supplier_profiles_mode_request": None,
            "supplier_profiles_supplier_request": None,
            "supplier_page_view": SUPPLIER_PAGE_VIEW_COMPARE,
            "supplier_page_view_last_rendered": SUPPLIER_PAGE_VIEW_COMPARE,
            "supplier_profiles_mode": SUPPLIER_PROFILE_MODE_EDITOR,
        }

        apply_requested_supplier_page_state(
            session_state,
            supplier_options=["Sony", "Acme"],
        )

        self.assertEqual(session_state["supplier_profiles_mode"], SUPPLIER_PROFILE_MODE_OVERVIEW)


if __name__ == "__main__":
    unittest.main()
