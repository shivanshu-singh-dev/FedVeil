import secrets
from datetime import datetime, timezone
from typing import List, Dict, Any
import psycopg2.errors
from src.storage.db_connection import get_connection


def register_client(client_id: str, name: str) -> str:
    """
    Registers a client with a new random 16-byte hex API key in RDS Postgres.
    Raises ValueError if client_id already exists.
    Returns the generated api_key.
    """
    cid_str = str(client_id).strip()
    name_str = str(name).strip()
    if not cid_str:
        raise ValueError("client_id cannot be empty.")

    api_key = secrets.token_hex(16)
    registered_at = datetime.now(timezone.utc).isoformat()

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO clients (client_id, name, api_key, registered_at)
                    VALUES (%s, %s, %s, %s)
                """, (cid_str, name_str, api_key, registered_at))
    except (psycopg2.errors.UniqueViolation, psycopg2.IntegrityError):
        conn.close()
        raise ValueError(f"Client '{cid_str}' is already registered.")
    finally:
        conn.close()

    return api_key


def is_valid_client(client_id: str, api_key: str) -> bool:
    """Checks if the client_id exists in RDS Postgres and the api_key matches."""
    if not client_id or not api_key:
        return False

    cid_str = str(client_id).strip()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT api_key FROM clients
                WHERE client_id = %s
            """, (cid_str,))
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return False

    stored_key = row["api_key"]
    return secrets.compare_digest(stored_key, str(api_key).strip())


def list_clients() -> List[Dict[str, Any]]:
    """
    Returns all registered clients from RDS Postgres (client_id, name, registered_at).
    Never includes api_key in the returned dictionary.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT client_id, name, registered_at
                FROM clients
                ORDER BY registered_at ASC
            """)
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "client_id": row["client_id"],
            "name": row["name"],
            "registered_at": row["registered_at"]
        }
        for row in rows
    ]
