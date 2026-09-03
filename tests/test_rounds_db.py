import os
import unittest
from src.storage.db_connection import get_connection, init_tables
from src.storage.rounds_db import log_round, get_latest_round


@unittest.skipUnless(os.environ.get("RDS_HOST"), "RDS_HOST not set — skipping RDS-dependent tests")
class TestRoundsDB(unittest.TestCase):
    def setUp(self):
        init_tables()
        conn = get_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM rounds;")
        conn.close()

    def test_get_latest_round_empty_returns_none(self):
        self.assertIsNone(get_latest_round())

    def test_log_round_and_get_latest(self):
        weights = [0.1, 0.2, 0.3]
        log_round(round=1, global_weights=weights, accuracy=0.92, loss=0.31, agg_ms=120.5)

        row = get_latest_round()
        self.assertIsNotNone(row)
        self.assertEqual(row["round"], 1)
        self.assertAlmostEqual(row["accuracy"], 0.92, places=4)
        self.assertAlmostEqual(row["loss"], 0.31, places=4)
        self.assertAlmostEqual(row["agg_ms"], 120.5, places=2)
        self.assertEqual(len(row["global_weights"]), 3)
        for expected, actual in zip(weights, row["global_weights"]):
            self.assertAlmostEqual(actual, expected, places=6)

    def test_log_multiple_rounds_returns_latest(self):
        log_round(round=1, global_weights=[0.1], accuracy=0.80, loss=0.50, agg_ms=100.0)
        log_round(round=2, global_weights=[0.2], accuracy=0.85, loss=0.40, agg_ms=95.0)
        log_round(round=3, global_weights=[0.3], accuracy=0.90, loss=0.30, agg_ms=90.0)

        row = get_latest_round()
        self.assertEqual(row["round"], 3)
        self.assertAlmostEqual(row["global_weights"][0], 0.3, places=6)

    def test_log_round_upsert_overwrites_cleanly(self):
        log_round(round=1, global_weights=[0.1, 0.2], accuracy=0.80, loss=0.50, agg_ms=100.0)
        # Re-run same round — should not raise, should overwrite
        log_round(round=1, global_weights=[0.5, 0.6], accuracy=0.88, loss=0.35, agg_ms=110.0)

        row = get_latest_round()
        self.assertEqual(row["round"], 1)
        self.assertAlmostEqual(row["global_weights"][0], 0.5, places=6)
        self.assertAlmostEqual(row["accuracy"], 0.88, places=4)

    def test_log_round_with_none_accuracy_and_loss(self):
        log_round(round=1, global_weights=[0.1], accuracy=None, loss=None, agg_ms=50.0)
        row = get_latest_round()
        self.assertIsNone(row["accuracy"])
        self.assertIsNone(row["loss"])


if __name__ == "__main__":
    unittest.main()
