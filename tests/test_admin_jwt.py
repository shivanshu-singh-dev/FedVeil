import os
import datetime
import unittest
from unittest.mock import patch, MagicMock
import jwt

TEST_SECRET = "test-secret-key-for-offline-tests-32-chars-long"
JWT_ALGORITHM = "HS256"

# Ensure environment variables are set and server imports cleanly without live DB
os.environ.setdefault("JWT_SECRET", TEST_SECRET)

with patch("src.storage.db_connection.init_tables"), \
     patch("src.storage.rounds_db.get_latest_round", return_value=None):
    from fastapi.testclient import TestClient
    import src.api.server as server_mod


def _make_token(username="admin", expire_hours=12):
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=expire_hours)
    return jwt.encode({"sub": username, "exp": expire}, TEST_SECRET, algorithm=JWT_ALGORITHM)


def _make_expired_token(username="admin"):
    expire = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    return jwt.encode({"sub": username, "exp": expire}, TEST_SECRET, algorithm=JWT_ALGORITHM)


class TestAdminLogin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(server_mod.app)

    @patch("src.api.server.verify_admin_credentials", return_value=True)
    def test_login_success_returns_token(self, _mock):
        resp = self.client.post("/api/admin/login", json={"username": "admin", "password": "correct"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("token", data)
        decoded = jwt.decode(data["token"], TEST_SECRET, algorithms=[JWT_ALGORITHM])
        self.assertEqual(decoded["sub"], "admin")

    @patch("src.api.server.verify_admin_credentials", return_value=False)
    def test_login_wrong_password_returns_401(self, _mock):
        resp = self.client.post("/api/admin/login", json={"username": "admin", "password": "wrong"})
        self.assertEqual(resp.status_code, 401)

    def test_admin_clients_without_token_returns_401(self):
        resp = self.client.get("/api/admin/clients")
        self.assertEqual(resp.status_code, 401)

    @patch("src.api.server.list_clients", return_value=[])
    @patch("src.api.server.get_cumulative_epsilon", return_value=0.0)
    def test_admin_clients_with_valid_token_returns_200(self, _eps, _list):
        token = _make_token()
        resp = self.client.get("/api/admin/clients", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 200)

    def test_admin_clients_with_expired_token_returns_401(self):
        expired = _make_expired_token()
        resp = self.client.get("/api/admin/clients", headers={"Authorization": f"Bearer {expired}"})
        self.assertEqual(resp.status_code, 401)

    def test_admin_clients_with_invalid_signature_returns_401(self):
        bad_token = jwt.encode(
            {"sub": "hacker", "exp": 9999999999},
            "wrong-secret-key-32-chars-long-xxx",
            algorithm=JWT_ALGORITHM
        )
        resp = self.client.get("/api/admin/clients", headers={"Authorization": f"Bearer {bad_token}"})
        self.assertEqual(resp.status_code, 401)

    @patch("src.api.server.register_client", return_value="abc123")
    def test_register_client_with_valid_token_returns_200(self, _reg):
        token = _make_token()
        resp = self.client.post(
            "/api/admin/register-client",
            json={"client_id": "node_1", "name": "Node One"},
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "registered")
        self.assertEqual(data["api_key"], "abc123")

    def test_register_client_without_token_returns_401(self):
        resp = self.client.post(
            "/api/admin/register-client",
            json={"client_id": "node_1", "name": "Node One"}
        )
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()
