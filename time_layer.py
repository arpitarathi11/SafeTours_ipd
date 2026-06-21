# time_layer.py
# Pure logic — no API key needed.
# Returns a time-based risk score 0.0–1.0 based on:
#   1. Time of day
#   2. Day type (weekday/weekend)
#   3. Mumbai festivals + public events

from datetime import datetime
import pytz

MUMBAI_TZ = pytz.timezone("Asia/Kolkata")

# ----------------------------
# Time of day buckets
# ----------------------------
# Each tuple: (start_hour, end_hour, score)
# 24hr format, end is exclusive
TIME_BUCKETS = [
    (5,  9,  0.2),   # early morning — low risk
    (9,  13, 0.2),   # morning — low risk
    (13, 17, 0.3),   # afternoon — mild
    (17, 20, 0.4),   # evening rush — moderate
    (20, 23, 0.6),   # night — elevated
    (23, 24, 0.8),   # late night — high
    (0,  2,  0.9),   # midnight — very high
    (2,  5,  0.7),   # pre-dawn — high
]

# ----------------------------
# Day type modifier
# ----------------------------
DAY_MODIFIERS = {
    "weekday":  0.0,   # no change
    "weekend":  0.1,   # slightly higher (crowds, nightlife)
    "holiday":  0.15,  # public holiday
    "festival": 0.2,   # major Mumbai festival
}

# ----------------------------
# Mumbai festivals 2024–2025
# Format: (month, day, type, name)
# ----------------------------
MUMBAI_FESTIVALS = [
    # 2025
    (1,  26, "holiday",  "Republic Day"),
    (2,  26, "festival", "Maha Shivratri"),
    (3,  14, "festival", "Holi"),
    (4,  14, "holiday",  "Ambedkar Jayanti"),
    (4,  18, "holiday",  "Good Friday"),
    (5,  1,  "holiday",  "Maharashtra Day"),
    (8,  15, "holiday",  "Independence Day"),
    (8,  16, "festival", "Ganesh Chaturthi"),   # ~10 day festival starts
    (8,  17, "festival", "Ganesh Chaturthi"),
    (8,  18, "festival", "Ganesh Chaturthi"),
    (8,  19, "festival", "Ganesh Chaturthi"),
    (8,  20, "festival", "Ganesh Chaturthi"),
    (8,  21, "festival", "Ganesh Chaturthi"),
    (8,  22, "festival", "Ganesh Chaturthi"),
    (8,  23, "festival", "Ganesh Chaturthi"),
    (8,  24, "festival", "Ganesh Chaturthi"),
    (8,  25, "festival", "Ganesh Chaturthi Visarjan"),  # peak crowd day
    (10, 2,  "holiday",  "Gandhi Jayanti"),
    (10, 20, "festival", "Navratri begins"),
    (10, 21, "festival", "Navratri"),
    (10, 22, "festival", "Navratri"),
    (10, 23, "festival", "Navratri"),
    (10, 24, "festival", "Navratri"),
    (10, 25, "festival", "Navratri"),
    (10, 26, "festival", "Navratri"),
    (10, 27, "festival", "Navratri"),
    (10, 28, "festival", "Navratri"),
    (10, 29, "festival", "Dussehra"),
    (11, 1,  "festival", "Diwali"),
    (11, 2,  "festival", "Diwali"),
    (11, 3,  "festival", "Diwali — Lakshmi Puja"),
    (11, 4,  "festival", "Diwali"),
    (11, 5,  "festival", "Diwali"),
    (12, 25, "holiday",  "Christmas"),
    (12, 31, "festival", "New Year's Eve"),     # peak risk night
]


def get_time_score(now: datetime = None) -> dict:
    """
    Returns time-based risk score 0.0–1.0.
    Optionally pass a datetime for testing; defaults to current Mumbai time.
    """

    if now is None:
        now = datetime.now(MUMBAI_TZ)
    else:
        # Make sure it's timezone-aware
        if now.tzinfo is None:
            now = MUMBAI_TZ.localize(now)

    hour       = now.hour
    weekday    = now.weekday()   # 0=Monday, 6=Sunday
    month      = now.month
    day        = now.day

    # --- Step 1: Time of day score ---
    time_score = 0.3  # default fallback
    for (start, end, score) in TIME_BUCKETS:
        if start <= hour < end:
            time_score = score
            break

    # --- Step 2: Day type ---
    day_type = "weekday"
    festival_name = None

    # Check festivals first (highest priority)
    for (f_month, f_day, f_type, f_name) in MUMBAI_FESTIVALS:
        if month == f_month and day == f_day:
            day_type = f_type
            festival_name = f_name
            break

    # If not a festival, check weekend
    if day_type == "weekday" and weekday >= 5:
        day_type = "weekend"

    # --- Step 3: Apply modifier ---
    modifier = DAY_MODIFIERS[day_type]
    final = min(1.0, time_score + modifier)

    return {
        "time_score": round(final, 3),
        "hour": hour,
        "day_type": day_type,
        "festival": festival_name,
        "weekday_name": now.strftime("%A"),
        "timestamp": now.strftime("%Y-%m-%d %H:%M IST")
    }


# --- Quick test ---
if __name__ == "__main__":
    from datetime import datetime

    test_cases = [
        {"label": "Monday 10am",          "dt": datetime(2025, 6, 2, 10, 0)},
        {"label": "Friday 11pm",          "dt": datetime(2025, 6, 6, 23, 0)},
        {"label": "Saturday 2am",         "dt": datetime(2025, 6, 7, 2,  0)},
        {"label": "Ganesh Chaturthi day", "dt": datetime(2025, 8, 16, 20, 0)},
        {"label": "New Year's Eve 11pm",  "dt": datetime(2025, 12, 31, 23, 0)},
        {"label": "Right now",            "dt": None},
    ]

    for t in test_cases:
        result = get_time_score(t["dt"])
        print(f"\n{t['label']}")
        print(f"  Time      : {result['timestamp']}")
        print(f"  Day type  : {result['day_type']} ({result['weekday_name']})")
        print(f"  Festival  : {result['festival']}")
        print(f"  Score     : {result['time_score']}")