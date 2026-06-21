"""
migrate_sos_log.py — Phase 6b (run once)

Reads the existing sos_log.json and inserts every entry into the
SQLite sos_log table, preserving the `cancelled` flag exactly.

Safe to re-run: uses INSERT OR IGNORE so duplicate rows are skipped
(keyed on user_id + fired_at, which is unique enough for this append-only log).

Usage:
    python migrate_sos_log.py              # uses default safety.db
    SAFETY_DB_PATH=prod.db python migrate_sos_log.py
"""

import json
import os
import sys

from db import init_db, get_conn

SOS_JSON_PATH = os.environ.get("SOS_JSON_PATH", "sos_log.json")


def migrate() -> None:
    if not os.path.exists(SOS_JSON_PATH):
        print(f"[migrate] {SOS_JSON_PATH} not found — nothing to migrate.")
        return

    with open(SOS_JSON_PATH, "r", encoding="utf-8") as f:
        raw = f.read().strip()

    if not raw:
        print("[migrate] sos_log.json is empty — nothing to migrate.")
        return

    # The file is an array of objects OR newline-delimited JSON objects
    try:
        entries = json.loads(raw)
        if isinstance(entries, dict):
            entries = [entries]
    except json.JSONDecodeError:
        # Try newline-delimited JSON
        entries = []
        for line in raw.splitlines():
            line = line.strip().rstrip(",")
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"[migrate] Skipping malformed line: {e}")

    if not entries:
        print("[migrate] No valid entries found in sos_log.json.")
        return

    init_db()
    conn = get_conn()

    inserted = 0
    skipped = 0

    with conn:
        for entry in entries:
            try:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO sos_log
                        (user_id, lat, lng, zone, score, fired_at, cancelled, cancelled_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.get("user_id"),
                        entry.get("lat"),
                        entry.get("lng"),
                        entry.get("zone"),
                        entry.get("score"),
                        entry.get("fired_at"),           # preserved exactly
                        1 if entry.get("cancelled") else 0,
                        entry.get("cancelled_at"),
                    ),
                )
                if cursor.rowcount:
                    inserted += 1
                else:
                    skipped += 1
            except Exception as e:
                print(f"[migrate] Error inserting entry {entry}: {e}")

    conn.close()

    print(f"[migrate] Done. Inserted: {inserted}, Skipped (duplicates): {skipped}")
    print(f"[migrate] sos_log.json is now retired. Do NOT delete it yet — keep as backup.")


if __name__ == "__main__":
    migrate()