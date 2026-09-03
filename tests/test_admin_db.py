import os
import unittest
from unittest.mock import patch, MagicMock
from src.storage.admin_db import create_admin, verify_admin_credentials
from src.storage.db_connection import get_connection, init_tables


@unittest.skipUnless(os.environ.get("RDS_HOST"), "RDS_HOST not set — skipping RDS-dependent tests")
class TestAdminDBLive(unittest.TestCase):
    """Live RDS integration tests; skipped when RDS_HOST is not set."""

    def setUp(self):
        init_tables()
        conn = get_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM admins;")
        conn.close()

    def test_create_and_verify_admin(self):
        create_admin("alice", "securepassword123")
        self.assertTrue(verify_admin_credentials("alice", "securepassword123"))

    def test_wrong_password_returns_false(self):
        create_admin("bob", "correctpassword")
        self.assertFalse(verify_admin_credentials("bob", "wrongpassword"))

    def test_nonexistent_user_returns_false(self):
        self.assertFalse(verify_admin_credentials("ghost", "anypassword"))

    def test_duplicate_username_raises_value_error(self):
        create_admin("charlie", "password123")
        with self.assertRaises(ValueError):
            create_admin("charlie", "differentpassword")


class TestAdminDBMocked(unittest.TestCase):
    """Offline unit tests using mocked psycopg2 connection."""

    @patch.dict("os.environ", {
        "RDS_HOST": "localhost", "RDS_PORT": "5432",
        "RDS_DBNAME": "testdb", "RDS_USER": "postgres", "RDS_PASSWORD": "password"
    })
    def test_create_admin_calls_insert(self):
        """create_admin() must hash the password and execute an INSERT."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch("psycopg2.connect", return_value=mock_conn):
            create_admin("testuser", "short-pw")

        self.assertTrue(mock_cur.execute.called)
        call_args = mock_cur.execute.call_args[0]
        self.assertIn("INSERT INTO admins", call_args[0])
        # First param is username
        self.assertEqual(call_args[1][0], "testuser")
        # Second param is a bcrypt hash (not plain text)
        stored_hash = call_args[1][1]
        self.assertNotEqual(stored_hash, "short-pw")
        self.assertTrue(stored_hash.startswith("$2"), f"Expected bcrypt hash, got: {stored_hash}")

    @patch.dict("os.environ", {
        "RDS_HOST": "localhost", "RDS_PORT": "5432",
        "RDS_DBNAME": "testdb", "RDS_USER": "postgres", "RDS_PASSWORD": "password"
    })
    def test_verify_missing_user_returns_false(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch("psycopg2.connect", return_value=mock_conn):
            result = verify_admin_credentials("nobody", "password")

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
