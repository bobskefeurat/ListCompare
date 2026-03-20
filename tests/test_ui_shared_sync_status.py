import unittest

from listcompare.interfaces.ui.session.shared_sync_status import store_shared_sync_status


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


if __name__ == "__main__":
    unittest.main()
