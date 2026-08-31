import os
import tempfile
import unittest
from src.storage.client_registry_db import register_client, is_valid_client, list_clients


class TestClientRegistry(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_privacy_log.db")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_register_and_validate_client(self):
        # Register a new client
        api_key = register_client("node_1", "Node One", db_path=self.db_path)
        self.assertIsInstance(api_key, str)
        self.assertEqual(len(api_key), 32)  # 16 bytes hex = 32 chars

        # Validate correct key
        self.assertTrue(is_valid_client("node_1", api_key, db_path=self.db_path))

        # Validate wrong key
        self.assertFalse(is_valid_client("node_1", "wrong_api_key_12345", db_path=self.db_path))

        # Validate non-existent client
        self.assertFalse(is_valid_client("non_existent", api_key, db_path=self.db_path))

    def test_duplicate_registration_raises_error(self):
        register_client("node_dup", "Duplicate Node", db_path=self.db_path)
        with self.assertRaises(ValueError):
            register_client("node_dup", "Duplicate Node Again", db_path=self.db_path)

    def test_list_clients_does_not_leak_api_key(self):
        key1 = register_client("client_a", "Alpha", db_path=self.db_path)
        key2 = register_client("client_b", "Beta", db_path=self.db_path)

        clients = list_clients(db_path=self.db_path)
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
