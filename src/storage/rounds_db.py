import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from src.storage.db_connection import get_connection


def log_round(
    round: int,
    global_weights: list,
    accuracy: Optional[float],
    loss: Optional[float],
    agg_ms: float
) -> None:
    """
    Inserts or updates a row in the rounds table.
    Uses ON CONFLICT (round) DO UPDATE so re-running a round overwrites cleanly.
    """
    conn = get_connection()
    logged_at = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO rounds (round, global_weights, accuracy, loss, agg_ms, logged_at)
                    VALUES (%s, %s::jsonb, %s, %s, %s, %s)
                    ON CONFLICT (round) DO UPDATE
                        SET global_weights = EXCLUDED.global_weights,
                            accuracy = EXCLUDED.accuracy,
                            loss = EXCLUDED.loss,
                            agg_ms = EXCLUDED.agg_ms,
                            logged_at = EXCLUDED.logged_at
                """, (
                    int(round),
                    json.dumps([float(w) for w in global_weights]),
                    float(accuracy) if accuracy is not None else None,
                    float(loss) if loss is not None else None,
                    float(agg_ms),
                    logged_at
                ))
    finally:
        conn.close()


def get_latest_round() -> Optional[Dict[str, Any]]:
    """
    Returns the row with the highest round number, or None if the table is empty.
    The global_weights field is returned as a Python list (deserialized from JSONB).
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT round, global_weights, accuracy, loss, agg_ms, logged_at
                FROM rounds
                ORDER BY round DESC
                LIMIT 1
            """)
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    result = dict(row)
    # global_weights comes back from JSONB as a Python list already via psycopg2
    if isinstance(result.get("global_weights"), str):
        result["global_weights"] = json.loads(result["global_weights"])
    return result
