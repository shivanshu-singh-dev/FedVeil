import os
import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "privacy_log.db")


def get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Returns a SQLite connection and ensures the table exists."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS privacy_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT,
                round INTEGER,
                epsilon_this_round REAL,
                cumulative_epsilon REAL,
                clip_bound REAL,
                noise_scale REAL,
                delta REAL,
                logged_at TEXT
            )
        """)
    return conn


def log_epsilon(
    client_id: str,
    round: int,
    epsilon_this_round: float,
    cumulative_epsilon: float,
    clip_bound: float,
    noise_scale: float,
    delta: float,
    db_path: str = DB_PATH
) -> int:
    """Inserts one privacy log record with UTC timestamp."""
    conn = get_db_connection(db_path)
    logged_at = datetime.now(timezone.utc).isoformat()
    with conn:
        cursor = conn.execute("""
            INSERT INTO privacy_log (
                client_id, round, epsilon_this_round, cumulative_epsilon,
                clip_bound, noise_scale, delta, logged_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(client_id),
            int(round),
            float(epsilon_this_round),
            float(cumulative_epsilon),
            float(clip_bound),
            float(noise_scale),
            float(delta),
            logged_at
        ))
        row_id = cursor.lastrowid
    conn.close()
    return row_id


def get_cumulative_epsilon(client_id: str, db_path: str = DB_PATH) -> float:
    """Returns the latest cumulative_epsilon for that client (0.0 if none logged yet)."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT cumulative_epsilon FROM privacy_log
        WHERE client_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (str(client_id),))
    row = cursor.fetchone()
    conn.close()
    if row:
        return float(row["cumulative_epsilon"])
    return 0.0


def get_all_privacy_logs(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Returns all rows from privacy_log, most recent first."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, client_id, round, epsilon_this_round, cumulative_epsilon,
               clip_bound, noise_scale, delta, logged_at
        FROM privacy_log
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
