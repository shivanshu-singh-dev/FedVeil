import os
import unittest
from src.storage.db_connection import get_connection, init_tables
from src.storage.client_registry_db import register_client, is_valid_client, list_clients


@unittest.skipUnless(os.environ.get("RDS_HOST"), "RDS_HOST not set — skipping RDS-dependent tests")
class TestClientRegistry(unittest.TestCase):
    def setUp(self):
        init_tables()
        conn = get_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM privacy_log;")
                cur.execute("DELETE FROM clients;")
        conn.close()

    def test_register_and_validate_client(self):
        # Register a new client
        api_key = register_client("node_1", "Node One")
        self.assertIsInstance(api_key, str)
        self.assertEqual(len(api_key), 32)  # 16 bytes hex = 32 chars

        # Validate correct key
        self.assertTrue(is_valid_client("node_1", api_key))

        # Validate wrong key
        self.assertFalse(is_valid_client("node_1", "wrong_api_key_12345"))

        # Validate non-existent client
        self.assertFalse(is_valid_client("non_existent", api_key))

    def test_duplicate_registration_raises_error(self):
        register_client("node_dup", "Duplicate Node")
        with self.assertRaises(ValueError):
            register_client("node_dup", "Duplicate Node Again")

    def test_list_clients_does_not_leak_api_key(self):
        key1 = register_client("client_a", "Alpha")
        key2 = register_client("client_b", "Beta")

        clients = list_clients()
        self.assertEqual(len(clients), 2)

        for c in clients:
            self.assertIn("client_id", c)
            self.assertIn("name", c)
            self.assertIn("registered_at", c)
            self.assertNotIn("api_key", c)
            self.assertNotIn(key1, str(c))
            self.assertNotIn(key2, str(c))


if __name__ == "__main__":
    unittest.main()
