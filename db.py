"""
db.py — Phase 6b
Single source of truth for the SQLite connection and schema.
All registries/trackers import get_conn() from here.
"""

import sqlite3
import os

DB_PATH = os.environ.get("SAFETY_DB_PATH", "safety.db")


def get_conn() -> sqlite3.Connection:
    """
    Return a thread-safe SQLite connection with WAL mode enabled.
    check_same_thread=False is safe here because every call site
    opens its own connection (or uses a thread-local pattern).
    Row factory set so callers get dict-like rows.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """
    Create all tables if they don't already exist.
    Safe to call on every app startup — fully idempotent.
    """
    conn = get_conn()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     TEXT PRIMARY KEY,
                user_name   TEXT,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS device_tokens (
                user_id     TEXT NOT NULL,
                push_token  TEXT NOT NULL,
                platform    TEXT NOT NULL DEFAULT 'fcm',
                updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, platform)
            );

            CREATE TABLE IF NOT EXISTS contacts (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       TEXT NOT NULL,
                contact_name  TEXT NOT NULL,
                phone         TEXT NOT NULL,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS zone_state (
                user_id     TEXT PRIMARY KEY,
                hex_id      TEXT,
                zone        TEXT,
                score       REAL,
                lat         REAL,
                lng         REAL,
                updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS checkin_state (
                user_id      TEXT PRIMARY KEY,
                attempts     INTEGER NOT NULL DEFAULT 0,
                last_sent_at TEXT,
                responded    INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS sos_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       TEXT NOT NULL,
                lat           REAL,
                lng           REAL,
                zone          TEXT,
                score         REAL,
                fired_at      TEXT NOT NULL DEFAULT (datetime('now')),
                cancelled     INTEGER NOT NULL DEFAULT 0,
                cancelled_at  TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_contacts_user
                ON contacts(user_id);

            CREATE INDEX IF NOT EXISTS idx_sos_log_user
                ON sos_log(user_id);
        """)
    conn.close()