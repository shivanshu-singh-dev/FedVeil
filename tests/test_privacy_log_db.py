import os
import tempfile
import unittest
from src.storage.privacy_log_db import log_epsilon, get_cumulative_epsilon, get_all_privacy_logs


class TestPrivacyLogDB(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_privacy_log.db")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_log_and_get_cumulative_epsilon(self):
        # Initially zero
        self.assertEqual(get_cumulative_epsilon("client_1", db_path=self.db_path), 0.0)

        # Log round 1
        log_epsilon(
            client_id="client_1",
            round=1,
            epsilon_this_round=96.89,
            cumulative_epsilon=96.89,
            clip_bound=1.0,
            noise_scale=0.05,
            delta=1e-5,
            db_path=self.db_path
        )

        self.assertAlmostEqual(get_cumulative_epsilon("client_1", db_path=self.db_path), 96.89, places=2)

        # Log round 2
        log_epsilon(
            client_id="client_1",
            round=2,
            epsilon_this_round=96.89,
            cumulative_epsilon=193.78,
            clip_bound=1.0,
            noise_scale=0.05,
            delta=1e-5,
            db_path=self.db_path
        )

        self.assertAlmostEqual(get_cumulative_epsilon("client_1", db_path=self.db_path), 193.78, places=2)

        # Separate client
        self.assertEqual(get_cumulative_epsilon("client_2", db_path=self.db_path), 0.0)

        logs = get_all_privacy_logs(db_path=self.db_path)
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]["round"], 2)  # Most recent first


if __name__ == "__main__":
    unittest.main()
