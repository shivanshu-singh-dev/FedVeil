import os
import sqlite3
import secrets
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "privacy_log.db")


def get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Returns a SQLite connection and ensures the clients table exists."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                client_id TEXT PRIMARY KEY,
                name TEXT,
                api_key TEXT,
                registered_at TEXT
            )
        """)
    return conn


def register_client(client_id: str, name: str, db_path: str = DB_PATH) -> str:
    """
    Registers a client with a new random 16-byte hex API key.
    Raises ValueError if client_id already exists.
    Returns the generated api_key.
    """
    cid_str = str(client_id).strip()
    name_str = str(name).strip()
    if not cid_str:
        raise ValueError("client_id cannot be empty.")

    api_key = secrets.token_hex(16)
    registered_at = datetime.now(timezone.utc).isoformat()

    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("""
                INSERT INTO clients (client_id, name, api_key, registered_at)
                VALUES (?, ?, ?, ?)
            """, (cid_str, name_str, api_key, registered_at))
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError(f"Client '{cid_str}' is already registered.")
    finally:
        conn.close()

    return api_key


def is_valid_client(client_id: str, api_key: str, db_path: str = DB_PATH) -> bool:
    """Checks if the client_id exists and the api_key matches."""
    if not client_id or not api_key:
        return False

    cid_str = str(client_id).strip()
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT api_key FROM clients
        WHERE client_id = ?
    """, (cid_str,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return False

    stored_key = row["api_key"]
    return secrets.compare_digest(stored_key, str(api_key).strip())


def list_clients(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """
    Returns all registered clients (client_id, name, registered_at).
    Never includes api_key in the returned dictionary.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT client_id, name, registered_at
        FROM clients
        ORDER BY registered_at ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "client_id": row["client_id"],
            "name": row["name"],
            "registered_at": row["registered_at"]
        }
        for row in rows
    ]
