import unittest
from unittest.mock import MagicMock, patch
import psycopg2.extras
from src.storage import db_connection, client_registry_db, privacy_log_db


class TestStorageMock(unittest.TestCase):
    @patch.dict("os.environ", {
        "RDS_HOST": "localhost",
        "RDS_PORT": "5432",
        "RDS_DBNAME": "testdb",
        "RDS_USER": "postgres",
        "RDS_PASSWORD": "password"
    })
    @patch("psycopg2.connect")
    def test_init_tables(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        db_connection.init_tables()

        self.assertTrue(mock_connect.called)
        self.assertEqual(mock_cur.execute.call_count, 2)
        mock_conn.close.assert_called_once()

    @patch.dict("os.environ", {
        "RDS_HOST": "localhost",
        "RDS_PORT": "5432",
        "RDS_DBNAME": "testdb",
        "RDS_USER": "postgres",
        "RDS_PASSWORD": "password"
    })
    @patch("psycopg2.connect")
    def test_register_and_list_clients(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        # Test register
        api_key = client_registry_db.register_client("client_1", "Client Node 1")
        self.assertEqual(len(api_key), 32)
        mock_cur.execute.assert_called_once()

        # Test list clients
        mock_cur.fetchall.return_value = [
            {"client_id": "client_1", "name": "Client Node 1", "registered_at": "2026-08-31T00:00:00Z"}
        ]
        clients = client_registry_db.list_clients()
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0]["client_id"], "client_1")
        self.assertNotIn("api_key", clients[0])

    @patch.dict("os.environ", {
        "RDS_HOST": "localhost",
        "RDS_PORT": "5432",
        "RDS_DBNAME": "testdb",
        "RDS_USER": "postgres",
        "RDS_PASSWORD": "password"
    })
    @patch("psycopg2.connect")
    def test_privacy_log_operations(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchone.return_value = {"id": 1, "cumulative_epsilon": 96.89}

        # Log epsilon
        row_id = privacy_log_db.log_epsilon(
            client_id="client_1",
            round=1,
            epsilon_this_round=96.89,
            cumulative_epsilon=96.89,
            clip_bound=1.0,
            noise_scale=0.05,
            delta=1e-5
        )
        self.assertEqual(row_id, 1)

        # Get cumulative epsilon
        cum_eps = privacy_log_db.get_cumulative_epsilon("client_1")
        self.assertEqual(cum_eps, 96.89)


if __name__ == "__main__":
    unittest.main()
