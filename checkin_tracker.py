"""
checkin_tracker.py — Phase 6b
SQLite-backed replacement for the in-memory dict.
Public method signatures are IDENTICAL to the Phase 5 version.
"""

from db import get_conn


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def reset_checkin(user_id: str) -> None:
    """Called on every /update-location — clears check-in state for the user."""
    conn = get_conn()
    with conn:
        conn.execute(
            """
            INSERT INTO checkin_state (user_id, attempts, last_sent_at, responded)
            VALUES (?, 0, NULL, 0)
            ON CONFLICT(user_id)
            DO UPDATE SET
                attempts     = 0,
                last_sent_at = NULL,
                responded    = 0
            """,
            (user_id,),
        )
    conn.close()


def record_checkin_sent(user_id: str) -> int:
    """
    Increment attempt counter and record timestamp.
    Returns the new attempt count.
    """
    conn = get_conn()
    with conn:
        conn.execute(
            """
            INSERT INTO checkin_state (user_id, attempts, last_sent_at, responded)
            VALUES (?, 1, datetime('now'), 0)
            ON CONFLICT(user_id)
            DO UPDATE SET
                attempts     = attempts + 1,
                last_sent_at = datetime('now'),
                responded    = 0
            """,
            (user_id,),
        )
        row = conn.execute(
            "SELECT attempts FROM checkin_state WHERE user_id = ?", (user_id,)
        ).fetchone()
    conn.close()
    return row["attempts"] if row else 1


def record_checkin_response(user_id: str) -> None:
    """User tapped check-in — mark responded and reset attempts."""
    conn = get_conn()
    with conn:
        conn.execute(
            """
            INSERT INTO checkin_state (user_id, attempts, last_sent_at, responded)
            VALUES (?, 0, NULL, 1)
            ON CONFLICT(user_id)
            DO UPDATE SET
                attempts  = 0,
                responded = 1
            """,
            (user_id,),
        )
    conn.close()


def get_checkin_state(user_id: str) -> dict:
    """
    Return current check-in state dict.
    Keys: attempts (int), last_sent_at (str|None), responded (bool).
    Returns default/zeroed state if user has no record yet.
    """
    conn = get_conn()
    row = conn.execute(
        "SELECT attempts, last_sent_at, responded FROM checkin_state WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()

    if row:
        return {
            "attempts": row["attempts"],
            "last_sent_at": row["last_sent_at"],
            "responded": bool(row["responded"]),
        }
    return {"attempts": 0, "last_sent_at": None, "responded": False}


def has_responded(user_id: str) -> bool:
    """Convenience: did the user respond to the last check-in?"""
    return get_checkin_state(user_id)["responded"]


# ---------------------------------------------------------------------------
# Shim — keeps main.py's `checkin_tracker.record_response(...)` calls working
# ---------------------------------------------------------------------------
class _Tracker:
    def record_response(self, user_id: str) -> None:
        record_checkin_response(user_id)

    def record_sent(self, user_id: str) -> int:
        return record_checkin_sent(user_id)

    def reset(self, user_id: str) -> None:
        reset_checkin(user_id)

    def get_state(self, user_id: str) -> dict:
        return get_checkin_state(user_id)

    def has_responded(self, user_id: str) -> bool:
        return has_responded(user_id)

tracker = _Tracker()