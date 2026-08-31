import os
import unittest
from unittest.mock import patch
from src.storage.db_connection import get_connection


class TestDBConnection(unittest.TestCase):
    def test_missing_env_vars_raises_runtime_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                get_connection()
            msg = str(ctx.exception)
            self.assertIn("Missing required RDS environment variable(s)", msg)
            self.assertIn("RDS_HOST", msg)
            self.assertIn("RDS_DBNAME", msg)
            self.assertIn("RDS_USER", msg)
            self.assertIn("RDS_PASSWORD", msg)


if __name__ == "__main__":
    unittest.main()
