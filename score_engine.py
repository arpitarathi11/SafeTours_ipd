"""
score_engine.py
Calculates final risk score (0-100) from all layers:
  - Crime   (40%)
  - Weather + events (20%)
  - Time of day + festivals (20%)
  - Infrastructure (15%)   <- Phase 6a: now reads real value from hex data
  - Solo traveller context (5%)
"""

from time_layer import get_time_score

# ----------------------------
# Zone thresholds
# ----------------------------
ZONE_THRESHOLDS = [
    (76, 100, "RED"),
    (56, 75,  "ORANGE"),
    (31, 55,  "YELLOW"),
    (0,  30,  "GREEN"),
]

# ----------------------------
# Weights
# ----------------------------
WEIGHTS = {
    "crime":   0.55,   # up from 0.40
    "weather": 0.05,   # down from 0.20
    "time":    0.25,   # up from 0.20
    "infra":   0.12,   # down from 0.15
    "context": 0.03,   # down from 0.05
}

# Phase 6a: fallback used ONLY when hex_scores_enriched.json hasn't been
# built yet, or for hex cells that fell through enrichment (network timeout).
_INFRA_SCORE_FALLBACK = 0.5


def score_to_zone(score: int) -> str:
    for (low, high, zone) in ZONE_THRESHOLDS:
        if low <= score <= high:
            return zone
    return "GREEN"


def calculate_base_score(
    crime_count:    int,
    crime_severity: float,                       # 0.0-1.0
    weather_score:  float = 0.0,                 # 0.0-1.0 from weather_layer
    infra_score:    float = _INFRA_SCORE_FALLBACK,  # 0.0-1.0 -- caller passes hex value
    solo_traveller: bool  = False,
    now=None                                     # datetime for testing; None = current time
) -> dict:
    """
    Returns final score (0-100), zone, and per-factor breakdown.

    Phase 6a change
    ---------------
    `infra_score` is no longer hardcoded here. main.py reads it from the
    enriched hex record and passes it in:

        hex_record  = HEX_LOOKUP[hex_id]
        infra_score = hex_record.get("infra_score", 0.5)
        result      = calculate_base_score(..., infra_score=infra_score)

    The default (0.5) is kept so that:
      - Old callers / Phase 1-5 test suites still work unchanged.
      - Cells that failed enrichment degrade gracefully, not crash.
    """

    # --- Crime score (0.0-1.0) ---
    crime_count_norm = min(crime_count / 10.0, 1.0)
    crime_score = (crime_count_norm * 0.6) + (crime_severity * 0.4)

    # --- Time score (0.0-1.0) ---
    time_result = get_time_score(now)
    time_score  = time_result["time_score"]

    # --- Context score (0.0-1.0) ---
    context_score = 0.6 if solo_traveller else 0.3

    # --- Weighted sum ---
    raw = (
        crime_score   * WEIGHTS["crime"]   +
        weather_score * WEIGHTS["weather"] +
        time_score    * WEIGHTS["time"]    +
        infra_score   * WEIGHTS["infra"]   +
        context_score * WEIGHTS["context"]
    )

    final_score = round(min(raw * 100, 100))
    zone        = score_to_zone(final_score)

    return {
        "score": final_score,
        "zone":  zone,
        "breakdown": {
            "crime_score":   round(crime_score, 3),
            "weather_score": round(weather_score, 3),
            "time_score":    round(time_score, 3),
            "infra_score":   round(infra_score, 3),
            "context_score": round(context_score, 3),
        },
        "time_detail": time_result,
    }


# --- Quick test ---
if __name__ == "__main__":
    from datetime import datetime

    cases = [
        {"label": "Low crime, Monday 10am -- default infra",
         "crime_count": 3,  "crime_sev": 0.2, "infra": 0.5,
         "dt": datetime(2025, 6, 2, 10, 0)},

        {"label": "High crime, Friday 11pm -- good infra (police nearby)",
         "crime_count": 35, "crime_sev": 0.8, "infra": 0.1,
         "dt": datetime(2025, 6, 6, 23, 0)},

        {"label": "Mid crime, Ganesh Chaturthi 8pm -- poor infra",
         "crime_count": 15, "crime_sev": 0.5, "infra": 0.9,
         "dt": datetime(2025, 8, 16, 20, 0)},

        {"label": "New Year's Eve midnight -- real infra score",
         "crime_count": 20, "crime_sev": 0.6, "infra": 0.35,
         "dt": datetime(2025, 12, 31, 23, 30)},
    ]

    for c in cases:
        r = calculate_base_score(
            crime_count=c["crime_count"],
            crime_severity=c["crime_sev"],
            weather_score=0.3,
            infra_score=c["infra"],
            now=c["dt"]
        )
        print(f"\n{c['label']}")
        print(f"  Score    : {r['score']} -> {r['zone']}")
        print(f"  Breakdown: {r['breakdown']}")
        print(f"  Festival : {r['time_detail']['festival']}")