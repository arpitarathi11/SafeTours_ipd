"""
device_registry.py — Phase 6b
SQLite-backed replacement for the in-memory dict.
Public method signatures are IDENTICAL to the Phase 5 version.
"""

from db import get_conn


def register_token(user_id: str, push_token: str, platform: str = "fcm") -> None:
    """Store or update a push token for a user."""
    conn = get_conn()
    with conn:
        conn.execute(
            """
            INSERT INTO device_tokens (user_id, push_token, platform, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(user_id, platform)
            DO UPDATE SET
                push_token = excluded.push_token,
                updated_at = excluded.updated_at
            """,
            (user_id, push_token, platform),
        )
    conn.close()


def get_token(user_id: str, platform: str = "fcm") -> str | None:
    """Return the push token for a user, or None if not registered."""
    conn = get_conn()
    row = conn.execute(
        "SELECT push_token FROM device_tokens WHERE user_id = ? AND platform = ?",
        (user_id, platform),
    ).fetchone()
    conn.close()
    return row["push_token"] if row else None


def remove_token(user_id: str, platform: str = "fcm") -> None:
    """Remove a push token (e.g. on logout)."""
    conn = get_conn()
    with conn:
        conn.execute(
            "DELETE FROM device_tokens WHERE user_id = ? AND platform = ?",
            (user_id, platform),
        )
    conn.close()


# ---------------------------------------------------------------------------
# Shim — keeps main.py's `device_registry.register(...)` calls working
# ---------------------------------------------------------------------------
class _Registry:
    def register(self, user_id: str, push_token: str, platform: str = "fcm", solo: bool = True) -> None:
        register_token(user_id, push_token, platform)

    def get(self, user_id: str, platform: str = "fcm") -> str | None:
        return get_token(user_id, platform)

    def remove(self, user_id: str, platform: str = "fcm") -> None:
        remove_token(user_id, platform)

registry = _Registry()