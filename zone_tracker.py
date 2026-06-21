"""
zone_tracker.py — Phase 6b
SQLite-backed replacement for the in-memory dict.
Public method signatures are IDENTICAL to the Phase 5 version.

Critical contract (Convention #7):
    get_user_state(user_id) must return a dict with at least:
        lat, lng, zone, score
    These four fields are the SOS payload source of truth.
"""

from db import get_conn


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _upsert_zone(conn, user_id, hex_id, zone, score, lat, lng) -> None:
    conn.execute(
        """
        INSERT INTO zone_state (user_id, hex_id, zone, score, lat, lng, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(user_id)
        DO UPDATE SET
            hex_id     = excluded.hex_id,
            zone       = excluded.zone,
            score      = excluded.score,
            lat        = excluded.lat,
            lng        = excluded.lng,
            updated_at = excluded.updated_at
        """,
        (user_id, hex_id, zone, score, lat, lng),
    )


def _get_row(conn, user_id):
    return conn.execute(
        "SELECT * FROM zone_state WHERE user_id = ?", (user_id,)
    ).fetchone()


# ---------------------------------------------------------------------------
# Public API (identical signatures to Phase 5)
# ---------------------------------------------------------------------------

def update_user_zone(
    user_id: str,
    hex_id: str,
    zone: str,
    score: float,
    lat: float,
    lng: float,
) -> dict:
    """
    Persist the user's current zone.  Returns a dict describing the transition:
        {
            "previous_zone": str | None,
            "current_zone":  str,
            "transition":    "none" | "escalation" | "de-escalation" | "lateral",
            "direction":     "worse" | "better" | "same",
        }
    """
    conn = get_conn()
    old_row = _get_row(conn, user_id)
    previous_zone = old_row["zone"] if old_row else None

    with conn:
        _upsert_zone(conn, user_id, hex_id, zone, score, lat, lng)

    conn.close()

    return _classify_transition(previous_zone, zone)


def get_user_state(user_id: str) -> dict | None:
    """
    Return current state dict or None if user has never been seen.
    Guaranteed keys when not None: lat, lng, zone, score, hex_id.
    """
    conn = get_conn()
    row = _get_row(conn, user_id)
    conn.close()
    return dict(row) if row else None


def clear_user_state(user_id: str) -> None:
    """Remove all zone state for a user (testing / account deletion)."""
    conn = get_conn()
    with conn:
        conn.execute("DELETE FROM zone_state WHERE user_id = ?", (user_id,))
    conn.close()


# ---------------------------------------------------------------------------
# Transition logic (pure, no DB)
# ---------------------------------------------------------------------------

_ZONE_ORDER = {"GREEN": 0, "YELLOW": 1, "ORANGE": 2, "RED": 3}


def _classify_transition(previous: str | None, current: str) -> dict:
    if previous is None or previous == current:
        return {
            "previous_zone": previous,
            "current_zone": current,
            "transition": "none",
            "direction": "same",
        }

    prev_rank = _ZONE_ORDER.get(previous, 0)
    curr_rank = _ZONE_ORDER.get(current, 0)

    if curr_rank > prev_rank:
        transition, direction = "escalation", "worse"
    elif curr_rank < prev_rank:
        transition, direction = "de-escalation", "better"
    else:
        transition, direction = "lateral", "same"

    return {
        "previous_zone": previous,
        "current_zone": current,
        "transition": transition,
        "direction": direction,
    }