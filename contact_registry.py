"""
contact_registry.py — Phase 6b
SQLite-backed replacement for the in-memory dict.
Public method signatures are IDENTICAL to the Phase 5 version.
"""

from db import get_conn


def register_contacts(user_id: str, contacts: list[dict]) -> None:
    """
    Replace all emergency contacts for a user.
    Each contact dict must have 'name' and 'phone' (E.164 validated upstream).
    """
    conn = get_conn()
    with conn:
        # Full replace — delete existing then insert fresh list
        conn.execute("DELETE FROM contacts WHERE user_id = ?", (user_id,))
        conn.executemany(
            """
            INSERT INTO contacts (user_id, contact_name, phone)
            VALUES (?, ?, ?)
            """,
            [(user_id, c["name"], c["phone"]) for c in contacts],
        )
    conn.close()


def get_contacts(user_id: str) -> list[dict]:
    """
    Return list of {name, phone} dicts for a user.
    Returns empty list if no contacts registered.
    """
    conn = get_conn()
    rows = conn.execute(
        "SELECT contact_name AS name, phone FROM contacts WHERE user_id = ? ORDER BY id",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Shim — keeps main.py's `contact_registry.register(...)` calls working
# ---------------------------------------------------------------------------
class _Registry:
    def register(self, user_id: str, user_name: str, contacts: list[dict]) -> None:
        register_contacts(user_id, contacts)

    def get(self, user_id: str) -> list[dict]:
        return get_contacts(user_id)

registry = _Registry()