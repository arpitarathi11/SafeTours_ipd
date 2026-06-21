Collection: hex_scores
  Document ID: H3 hex cell ID (e.g. "891f1d48003ffff")
  Fields:
    hex_id         (string)  — same as doc ID, e.g. "891f1d48003ffff"
    lat            (number)  — center lat of the hex
    lng            (number)  — center lng of the hex
    base_score     (number)  — raw crime score 0–100
    zone           (string)  — "GREEN" | "YELLOW" | "ORANGE" | "RED"
    crime_count    (number)  — raw incident count from NCRB
    crime_severity (number)  — weighted severity 0–1
    last_updated   (timestamp)

Collection: dynamic_events  ← Phase 2, ignore for now
Collection: user_sessions   ← Phase 4, ignore for now
