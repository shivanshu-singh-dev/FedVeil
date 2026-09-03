from datetime import datetime, timezone
from typing import Optional
import psycopg2.errors
from passlib.context import CryptContext
from src.storage.db_connection import get_connection

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_admin(username: str, password: str) -> None:
    """
    Hashes the password with bcrypt and inserts a new admin row.
    Raises ValueError if the username already exists.
    """
    username = username.strip()
    if not username:
        raise ValueError("username cannot be empty.")

    password_hash = _pwd_context.hash(password)
    created_at = datetime.now(timezone.utc).isoformat()

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO admins (username, password_hash, created_at)
                    VALUES (%s, %s, %s)
                """, (username, password_hash, created_at))
    except (psycopg2.errors.UniqueViolation, psycopg2.IntegrityError):
        conn.close()
        raise ValueError(f"Admin '{username}' already exists.")
    finally:
        conn.close()


def verify_admin_credentials(username: str, password: str) -> bool:
    """
    Looks up the username in the admins table and verifies the password
    against the stored bcrypt hash. Returns False if username is not found.
    """
    if not username or not password:
        return False

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT password_hash FROM admins
                WHERE username = %s
            """, (username.strip(),))
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return False

    return _pwd_context.verify(password, row["password_hash"])
