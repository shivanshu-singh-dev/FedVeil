from datetime import datetime, timezone
from typing import List, Dict, Any
from src.storage.db_connection import get_connection


def log_epsilon(
    client_id: str,
    round: int,
    epsilon_this_round: float,
    cumulative_epsilon: float,
    clip_bound: float,
    noise_scale: float,
    delta: float
) -> int:
    """Inserts one privacy log record into RDS Postgres with UTC timestamp."""
    conn = get_connection()
    logged_at = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO privacy_log (
                        client_id, round, epsilon_this_round, cumulative_epsilon,
                        clip_bound, noise_scale, delta, logged_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
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
                row = cur.fetchone()
                row_id = row["id"] if row else None
    finally:
        conn.close()

    return row_id


def get_cumulative_epsilon(client_id: str) -> float:
    """Returns the latest cumulative_epsilon for that client from RDS Postgres (0.0 if none logged yet)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cumulative_epsilon FROM privacy_log
                WHERE client_id = %s
                ORDER BY id DESC
                LIMIT 1
            """, (str(client_id),))
            row = cur.fetchone()
    finally:
        conn.close()

    if row:
        return float(row["cumulative_epsilon"])
    return 0.0


def get_all_privacy_logs() -> List[Dict[str, Any]]:
    """Returns all rows from privacy_log in RDS Postgres, most recent first."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, client_id, round, epsilon_this_round, cumulative_epsilon,
                       clip_bound, noise_scale, delta, logged_at
                FROM privacy_log
                ORDER BY id DESC
            """)
            rows = cur.fetchall()
    finally:
        conn.close()

    return [dict(row) for row in rows]
