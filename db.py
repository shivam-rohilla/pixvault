"""
db.py — direct psycopg3 connections (no pool) for reliability on free-tier hosts.
"""
import uuid
import logging
from datetime import datetime, date

import psycopg
from psycopg.rows import dict_row

log = logging.getLogger(__name__)

_database_url: str = ""


def init_pool(database_url: str) -> None:
    """Store the connection URL (called init_pool for API compatibility)."""
    global _database_url
    if "sslmode" not in database_url:
        sep = "&" if "?" in database_url else "?"
        database_url += f"{sep}sslmode=require"
    if "connect_timeout" not in database_url:
        database_url += "&connect_timeout=10"
    _database_url = database_url
    log.info("DB URL configured (pool-free mode)")


def _connect():
    return psycopg.connect(_database_url, row_factory=dict_row, prepare_threshold=None)


# ── Type coercion ──────────────────────────────────────────────
def _cast(v):
    if isinstance(v, uuid.UUID):        return str(v)
    if isinstance(v, (datetime, date)): return v.isoformat()
    return v

def _row(r: dict) -> dict:
    return {k: _cast(v) for k, v in r.items()}


# ── Public helpers ─────────────────────────────────────────────
def query_all(sql: str, params=None) -> list[dict]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [_row(r) for r in cur.fetchall()]


def query_one(sql: str, params=None) -> dict | None:
    rows = query_all(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params=None) -> list[dict]:
    """INSERT / UPDATE / DELETE — returns RETURNING rows if any."""
    with _connect() as conn:
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
