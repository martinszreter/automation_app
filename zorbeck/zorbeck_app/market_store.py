"""Small, persistent marketplace store for the current single Railway replica.

SQLite runs on the mounted volume, with transactions and durable payment/event
keys. This module does not create a temporary fallback database in production.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException

from zorbeck_app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
 recovery_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'member',
 marketing INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 expires_at INTEGER NOT NULL, created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS listings (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id),
 status TEXT NOT NULL DEFAULT 'draft', data_json TEXT NOT NULL,
 review_note TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL,
 updated_at INTEGER NOT NULL, published_at INTEGER
);
CREATE INDEX IF NOT EXISTS listings_owner ON listings(owner_id);
CREATE TABLE IF NOT EXISTS photos (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id),
 listing_id TEXT REFERENCES listings(id), content BLOB NOT NULL,
 created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS saved (
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 property_id TEXT NOT NULL, PRIMARY KEY(user_id, property_id)
);
CREATE TABLE IF NOT EXISTS enquiries (
 id TEXT PRIMARY KEY, listing_id TEXT NOT NULL REFERENCES listings(id),
 buyer_id TEXT NOT NULL REFERENCES users(id), message TEXT NOT NULL,
 created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
 listing_id TEXT REFERENCES listings(id), kind TEXT NOT NULL,
 amount_cents INTEGER NOT NULL, payment_link_id TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending', session_id TEXT UNIQUE,
 payment_intent TEXT, created_at INTEGER NOT NULL, paid_at INTEGER,
 promotion_until INTEGER
);
CREATE INDEX IF NOT EXISTS orders_intent ON orders(payment_intent);
CREATE TABLE IF NOT EXISTS payment_events (
 id TEXT PRIMARY KEY, event_type TEXT NOT NULL, received_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS payment_blocks (
 payment_intent TEXT PRIMARY KEY, reason TEXT NOT NULL, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS payment_exceptions (
 session_id TEXT PRIMARY KEY, order_id TEXT, reason TEXT NOT NULL,
 created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS moderation (
 id INTEGER PRIMARY KEY AUTOINCREMENT, listing_id TEXT NOT NULL,
 admin_id TEXT NOT NULL, action TEXT NOT NULL, note TEXT NOT NULL, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rate_limits (
 key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS lead_outbox (
 id TEXT PRIMARY KEY, payload TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
 next_attempt INTEGER NOT NULL, delivered_at INTEGER
);
"""


def available() -> bool:
    return bool(settings.marketplace_db_path)


@lru_cache(maxsize=8)
def initialize(path: str) -> None:
    target = Path(path)
    # A missing volume must be an operational error, never a new temporary dir.
    if not target.is_absolute() or not target.parent.is_dir():
        raise RuntimeError("The persistent marketplace database directory is unavailable")
    with sqlite3.connect(path, timeout=10) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
    os.chmod(target, 0o600)


@contextmanager
def database(*, write: bool = False):
    path = settings.marketplace_db_path
    if not path:
        raise HTTPException(503, "Accounts are temporarily unavailable. Please try again shortly.")
    initialize(path)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=FULL")
    try:
        if write:
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def rate_limit(key: str, limit: int, seconds: int = 900) -> None:
    now = int(time.time())
    with database(write=True) as conn:
        conn.execute("DELETE FROM rate_limits WHERE expires_at < ?", (now,))
        row = conn.execute("SELECT count FROM rate_limits WHERE key=?", (key,)).fetchone()
        if row and row["count"] >= limit:
            raise HTTPException(429, "Please wait a few minutes before trying again.")
        conn.execute(
            "INSERT INTO rate_limits VALUES (?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1",
            (key, now + seconds),
        )


def enqueue_lead(conn, record_id: str, email: str, status: str, **extra) -> None:
    payload = {
        "app": "zorbeck", "venture": "zorbeck", "source": "zorbeck-marketplace",
        "email": email, "status": status, "email_verified": False,
        "consent_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **extra,
    }
    conn.execute("INSERT OR IGNORE INTO lead_outbox(id,payload,next_attempt) VALUES (?,?,?)",
                 (record_id, json.dumps(payload), int(time.time())))
