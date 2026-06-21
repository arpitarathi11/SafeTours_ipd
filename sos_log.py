"""
sos_log.py — Phase 6b
SQLite-backed replacement for the append-only sos_log.json file.
Public method signatures match the usage pattern in sos_handler.py / main.py.

The old sos_log.json is migrated by migrate_sos_log.py (run once).
After migration this module is the only writer.
"""

from db import get_conn


def append_sos(
    user_id: str,
    lat: float | None,
    lng: float | None,
    zone: str | None,
    score: float | None,
) -> int:
    """
    Write a new SOS event.  Returns the row id (used by cancel_sos).
    """
    conn = get_conn()
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO sos_log (user_id, lat, lng, zone, score, fired_at, cancelled)
            VALUES (?, ?, ?, ?, ?, datetime('now'), 0)
            """,
            (user_id, lat, lng, zone, score),
        )
        row_id = cursor.lastrowid
    conn.close()
    return row_id


def cancel_sos(sos_id: int) -> bool:
    """
    Mark a specific SOS row as cancelled.
    Returns True if a row was updated, False if the id didn't exist.
    """
    conn = get_conn()
    with conn:
        cursor = conn.execute(
            """
            UPDATE sos_log
            SET cancelled    = 1,
                cancelled_at = datetime('now')
            WHERE id = ? AND cancelled = 0
            """,
            (sos_id,),
        )
        updated = cursor.rowcount
    conn.close()
    return updated > 0


def get_latest_sos_id(user_id: str) -> int | None:
    """
    Return the id of the most recent uncancelled SOS for a user.
    Used by the /cancel-sos endpoint to find what to cancel.
    """
    conn = get_conn()
    row = conn.execute(
        """
        SELECT id FROM sos_log
        WHERE user_id = ? AND cancelled = 0
        ORDER BY fired_at DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    conn.close()
    return row["id"] if row else None


def get_sos_history(user_id: str, limit: int = 50) -> list[dict]:
    """Return recent SOS events for a user (admin/debug use)."""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT * FROM sos_log
        WHERE user_id = ?
        ORDER BY fired_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]