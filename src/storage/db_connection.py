import os
import psycopg2
import psycopg2.extras


def get_connection():
    """
    Connects to the AWS RDS Postgres database using environment variables.
    Returns a psycopg2 connection with RealDictCursor for dictionary-like row access.
    Raises RuntimeError if any required environment variable is missing.
    """
    host = os.environ.get("RDS_HOST")
    port = os.environ.get("RDS_PORT", "5432")
    dbname = os.environ.get("RDS_DBNAME")
    user = os.environ.get("RDS_USER")
    password = os.environ.get("RDS_PASSWORD")

    missing = []
    if not host:
        missing.append("RDS_HOST")
    if not dbname:
        missing.append("RDS_DBNAME")
    if not user:
        missing.append("RDS_USER")
    if not password:
        missing.append("RDS_PASSWORD")

    if missing:
        raise RuntimeError(
            f"Missing required RDS environment variable(s): {', '.join(missing)}. "
            "Please set RDS_HOST, RDS_DBNAME, RDS_USER, and RDS_PASSWORD."
        )

    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    return conn


def init_tables():
    """
    Initializes required Postgres tables (clients, privacy_log, rounds, admins)
    if they do not exist. Safe and idempotent to call on server startup.
    """
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS clients (
                    client_id TEXT PRIMARY KEY,
                    name TEXT,
                    api_key TEXT,
                    registered_at TEXT
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS privacy_log (
                    id SERIAL PRIMARY KEY,
                    client_id TEXT,
                    round INTEGER,
                    epsilon_this_round REAL,
                    cumulative_epsilon REAL,
                    clip_bound REAL,
                    noise_scale REAL,
                    delta REAL,
                    logged_at TEXT
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS rounds (
                    round INTEGER PRIMARY KEY,
                    global_weights JSONB,
                    accuracy REAL,
                    loss REAL,
                    agg_ms REAL,
                    logged_at TEXT
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT
                );
            """)
    conn.close()
