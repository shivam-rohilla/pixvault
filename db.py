"""
db.py — psycopg3 + connection pool for Supabase transaction pooler.
Pool reuses connections so we pay the SSL handshake only once, not per query.
"""
import uuid
from datetime import datetime, date

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None


def init_pool(database_url: str) -> None:
    global _pool

    # Supabase requires SSL
    if "sslmode" not in database_url:
        sep = "&" if "?" in database_url else "?"
        database_url += f"{sep}sslmode=require"

    _pool = ConnectionPool(
        database_url,
        min_size=1,
        max_size=5,           # stay within Supabase free-tier connection limit
        open=False,           # lazy connect — avoids blocking gunicorn worker startup
        kwargs={
            "row_factory": dict_row,
            "prepare_threshold": None,   # required: pooler blocks prepared stmts
        },
    )
    _pool.open(wait=False)    # open in background, don't block startup


# ── Type coercion ──────────────────────────────────────────────
def _cast(v):
    if isinstance(v, uuid.UUID):        return str(v)
    if isinstance(v, (datetime, date)): return v.isoformat()
    return v

def _row(r: dict) -> dict:
    return {k: _cast(v) for k, v in r.items()}


# ── Public helpers ─────────────────────────────────────────────
def query_all(sql: str, params=None) -> list[dict]:
    with _pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [_row(r) for r in cur.fetchall()]


def query_one(sql: str, params=None) -> dict | None:
    rows = query_all(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params=None) -> list[dict]:
    """INSERT / UPDATE / DELETE — returns RETURNING rows if any."""
    with _pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            try:
                return [_row(r) for r in cur.fetchall()]
            except psycopg.ProgrammingError:
                return []


def execute_one(sql: str, params=None) -> dict | None:
    rows = execute(sql, params)
    return rows[0] if rows else None
