# event_layer.py
# Polls NewsAPI for critical events near Mumbai.
# CRITICAL events → hard cap score to 100 immediately.
# NON-CRITICAL events → return a delta that adds to the score.

import requests
from datetime import datetime, timedelta

import os
NEWS_API_KEY = os.getenv("NEWS_API_KEY") # ← paste your key here
NEWS_URL = "https://newsapi.org/v2/everything"

# ----------------------------
# Keywords by severity
# ----------------------------
CRITICAL_KEYWORDS = [
    "riot", "flood", "landslide", "stampede",
    "explosion", "terrorist", "bomb", "shooting",
    "cyclone", "tsunami", "earthquake"
]

NON_CRITICAL_KEYWORDS = [
    "protest", "fire", "accident", "traffic block",
    "waterlogging", "strike", "road closed"
]

# How long an event stays active after article publish time
EVENT_TTL_HOURS = {
    "critical": 12,
    "non_critical": 6
}


def check_active_events() -> dict:
    """
    Pulls last 24hr news mentioning Mumbai + any keyword.
    Returns:
        {
            "hard_cap": True/False,       # True = score → 100 immediately
            "delta": 0.0–0.3,             # added to score if not hard cap
            "reason": "string or None",   # shown in reason card
            "events": [...]               # list of matched events
        }
    """

    since = (datetime.utcnow() - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

    all_keywords = CRITICAL_KEYWORDS + NON_CRITICAL_KEYWORDS
    query = "Mumbai AND (" + " OR ".join(all_keywords) + ")"

    try:
        response = requests.get(
            NEWS_URL,
            params={
                "q": query,
                "from": since,
                "sortBy": "publishedAt",
                "language": "en",
                "apiKey": NEWS_API_KEY
            },
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        articles = data.get("articles", [])

    except requests.exceptions.RequestException as e:
        print(f"[event_layer] API error: {e} — skipping event layer")
        return _no_event()

    # ----------------------------
    # Classify each article
    # ----------------------------
    matched_critical     = []
    matched_non_critical = []

    for article in articles:
        title       = (article.get("title") or "").lower()
        description = (article.get("description") or "").lower()
        text        = title + " " + description

        # Skip if not Mumbai-related
        if "mumbai" not in text:
            continue

        # Check critical first
        for kw in CRITICAL_KEYWORDS:
            if kw in text:
                matched_critical.append({
                    "keyword": kw,
                    "title": article.get("title"),
                    "published": article.get("publishedAt"),
                    "source": article.get("source", {}).get("name")
                })
                break  # one match per article is enough

        # Check non-critical
        for kw in NON_CRITICAL_KEYWORDS:
            if kw in text:
                matched_non_critical.append({
                    "keyword": kw,
                    "title": article.get("title"),
                    "published": article.get("publishedAt"),
                    "source": article.get("source", {}).get("name")
                })
                break

    # ----------------------------
    # Decision logic
    # ----------------------------

    # CRITICAL match → hard cap, score goes to 100
    if matched_critical:
        top = matched_critical[0]
        return {
            "hard_cap": True,
            "delta": 0.0,
            "reason": f"{top['keyword'].upper()} reported near Mumbai ({top['source']})",
            "events": matched_critical
        }

    # NON-CRITICAL match → add delta to score
    if matched_non_critical:
        # More matches = higher delta, capped at 0.3
        delta = min(0.3, len(matched_non_critical) * 0.1)
        top = matched_non_critical[0]
        return {
            "hard_cap": False,
            "delta": round(delta, 2),
            "reason": f"{top['keyword'].capitalize()} reported near Mumbai ({top['source']})",
            "events": matched_non_critical
        }

    # Nothing found
    return _no_event()


def _no_event() -> dict:
    return {
        "hard_cap": False,
        "delta": 0.0,
        "reason": None,
        "events": []
    }


# --- Quick test ---
if __name__ == "__main__":
    print("Checking active events near Mumbai...")
    result = check_active_events()

    print(f"\nHard cap : {result['hard_cap']}")
    print(f"Delta    : {result['delta']}")
    print(f"Reason   : {result['reason']}")
    print(f"Events   : {len(result['events'])} matched")

    for e in result["events"][:3]:
        print(f"\n  [{e['keyword'].upper()}] {e['title']}")
        print(f"  Source: {e['source']} | Published: {e['published']}")