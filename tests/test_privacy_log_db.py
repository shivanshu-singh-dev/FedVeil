import os
import unittest
from src.storage.db_connection import get_connection, init_tables
from src.storage.privacy_log_db import log_epsilon, get_cumulative_epsilon, get_all_privacy_logs


@unittest.skipUnless(os.environ.get("RDS_HOST"), "RDS_HOST not set — skipping RDS-dependent tests")
class TestPrivacyLogDB(unittest.TestCase):
    def setUp(self):
        init_tables()
        conn = get_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM privacy_log;")
                cur.execute("DELETE FROM clients;")
        conn.close()

    def test_log_and_get_cumulative_epsilon(self):
        # Initially zero
        self.assertEqual(get_cumulative_epsilon("client_1"), 0.0)

        # Log round 1
        log_epsilon(
            client_id="client_1",
            round=1,
            epsilon_this_round=96.89,
            cumulative_epsilon=96.89,
            clip_bound=1.0,
            noise_scale=0.05,
            delta=1e-5
        )

        self.assertAlmostEqual(get_cumulative_epsilon("client_1"), 96.89, places=2)

        # Log round 2
        log_epsilon(
            client_id="client_1",
            round=2,
            epsilon_this_round=96.89,
            cumulative_epsilon=193.78,
            clip_bound=1.0,
            noise_scale=0.05,
            delta=1e-5
        )

        self.assertAlmostEqual(get_cumulative_epsilon("client_1"), 193.78, places=2)

        # Separate client
        self.assertEqual(get_cumulative_epsilon("client_2"), 0.0)

        logs = get_all_privacy_logs()
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]["round"], 2)  # Most recent first


if __name__ == "__main__":
    unittest.main()
