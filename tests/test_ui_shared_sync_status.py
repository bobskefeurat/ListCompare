import unittest
from unittest.mock import Mock

from listcompare.interfaces.ui.services.shared_sync import SharedSyncStatus
from listcompare.interfaces.ui.session.shared_sync_status import (
    maybe_run_auto_shared_sync,
    store_shared_sync_status,
)


class SharedSyncStatusSessionTests(unittest.TestCase):
    def test_store_shared_sync_status_persists_source_and_conflicts(self) -> None:
        session_state: dict[str, object] = {}

        store_shared_sync_status(
            session_state,
            level="warning",
            message="Synkvarning",
            profile_conflicts=("EM Nordic",),
            source="  Appstart  ",
        )

        self.assertEqual(session_state["shared_sync_status_level"], "warning")
        self.assertEqual(session_state["shared_sync_status_message"], "Synkvarning")
        self.assertEqual(session_state["shared_sync_profile_conflicts"], ("EM Nordic",))
        self.assertEqual(session_state["shared_sync_status_source"], "Appstart")

    def test_store_shared_sync_status_clears_blank_source(self) -> None:
        session_state: dict[str, object] = {
            "shared_sync_status_source": "Old source",
        }

        store_shared_sync_status(
            session_state,
            level="success",
            message="Synkad",
            source="   ",
        )

        self.assertIsNone(session_state["shared_sync_status_source"])

    def test_maybe_run_auto_shared_sync_uses_cooldown_for_same_and_subset_targets(self) -> None:
        session_state: dict[str, object] = {}
        sync_runner = Mock(
            return_value=SharedSyncStatus(
                level="success",
                message="Synkad",
                shared_folder=r"G:\Min enhet\ListCompareShared",
            )
        )

        first = maybe_run_auto_shared_sync(
            session_state,
            sync_runner=sync_runner,
            targets=("supplier_index.txt", "brand_index.txt", "supplier_transform_profiles.json"),
            min_interval_seconds=10.0,
            now=100.0,
        )
        second = maybe_run_auto_shared_sync(
            session_state,
            sync_runner=sync_runner,
            targets=("brand_index.txt", "supplier_index.txt"),
            min_interval_seconds=10.0,
            now=105.0,
        )
        third = maybe_run_auto_shared_sync(
            session_state,
            sync_runner=sync_runner,
            targets=("supplier_transform_profiles.json",),
            min_interval_seconds=10.0,
            now=106.0,
        )
        fourth = maybe_run_auto_shared_sync(
            session_state,
            sync_runner=sync_runner,
            targets=("supplier_index.txt", "brand_index.txt", "supplier_transform_profiles.json"),
            min_interval_seconds=10.0,
            now=111.0,
        )

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertIsNone(third)
        self.assertIsNotNone(fourth)
        self.assertEqual(sync_runner.call_count, 2)


if __name__ == "__main__":
    unittest.main()
