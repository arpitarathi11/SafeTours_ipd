# reason_card.py
# Builds the human-readable reason card shown to the user.
# Max 3 reasons, ranked by contribution to final score.
# UX copy is calm, not alarmist.
# Gender differentiation is NEVER surfaced here.

ZONE_COLORS = {
    "GREEN":  "🟢",
    "YELLOW": "🟡",
    "ORANGE": "🟠",
    "RED":    "🔴",
}

# ----------------------------
# Reason templates per factor
# ----------------------------

def _crime_reason(crime_count, crime_severity):
    if crime_count > 30 or crime_severity > 0.75:
        return f"High incident reports in this area (NCRB data)"
    elif crime_count > 15 or crime_severity > 0.5:
        return f"Moderate incident history in this area"
    elif crime_count > 5:
        return f"Some past incidents recorded nearby"
    return None


def _weather_reason(weather_score, weather_condition):
    if weather_score > 0.7:
        return f"Severe weather alert: {weather_condition}"
    elif weather_score > 0.4:
        return f"Adverse weather conditions: {weather_condition}"
    elif weather_score > 0.2:
        return f"Weather advisory in effect: {weather_condition}"
    return None


def _time_reason(time_detail):
    hour      = time_detail.get("hour", 12)
    day_type  = time_detail.get("day_type", "weekday")
    festival  = time_detail.get("festival")

    if festival:
        return f"Festival crowds active: {festival}"
    if hour >= 23 or hour < 2:
        return "Late night hours increase risk"
    if hour >= 2 and hour < 5:
        return "Pre-dawn hours — reduced visibility and activity"
    if hour >= 20:
        return "Night hours in effect"
    if day_type == "weekend":
        return "Weekend — higher crowd activity"
    return None


def _event_reason(event_reason, event_delta):
    if event_reason and event_delta > 0:
        return event_reason
    return None


def _infra_reason(infra_score):
    if infra_score > 0.7:
        return "Limited police/hospital coverage nearby"
    elif infra_score > 0.5:
        return "Reduced emergency service proximity"
    return None


# ----------------------------
# Main builder
# ----------------------------

def build_reason_card(
    zone:              str,
    score:             int,
    crime_count:       int,
    crime_severity:    float,
    weather_score:     float,
    weather_condition: str,
    time_detail:       dict,
    event_reason:      str   = None,
    event_delta:       float = 0.0,
    infra_score:       float = 0.5,
    hex_name:          str   = "This area",
    updated_mins_ago:  int   = 0,
) -> dict:
    """
    Returns a reason card dict with:
      - zone, score, emoji
      - up to 3 human-readable reasons (ranked by severity)
      - updated_at string
      - raw reasons list for API consumers
    """

    # Collect all candidate reasons with a weight (higher = more important)
    candidates = []

    r = _crime_reason(crime_count, crime_severity)
    if r:
        weight = crime_count / 50.0 * 0.4 + crime_severity * 0.4
        candidates.append((weight, r))

    r = _weather_reason(weather_score, weather_condition)
    if r:
        candidates.append((weather_score * 0.2, r))

    r = _time_reason(time_detail)
    if r:
        candidates.append((time_detail.get("time_score", 0.3) * 0.2, r))

    r = _event_reason(event_reason, event_delta)
    if r:
        candidates.append((0.9, r))   # events always rank high

    r = _infra_reason(infra_score)
    if r:
        candidates.append((infra_score * 0.15, r))

    # Sort by weight descending, take top 3
    candidates.sort(key=lambda x: x[0], reverse=True)
    top_reasons = [reason for (_, reason) in candidates[:3]]

    # If no reasons generated (GREEN zone), give a positive message
    if not top_reasons:
        top_reasons = ["No significant risk factors detected"]

    # Updated-at string
    if updated_mins_ago == 0:
        updated_str = "just now"
    elif updated_mins_ago == 1:
        updated_str = "1 min ago"
    else:
        updated_str = f"{updated_mins_ago} min ago"

    emoji = ZONE_COLORS.get(zone, "⚪")

    return {
        "zone":        zone,
        "score":       score,
        "emoji":       emoji,
        "hex_name":    hex_name,
        "reasons":     top_reasons,
        "updated_str": updated_str,
        "display": _format_display(zone, score, hex_name, top_reasons, updated_str, emoji),
    }


def _format_display(zone, score, hex_name, reasons, updated_str, emoji) -> str:
    """Human-readable card for logging / debug / notification body."""
    lines = [
        f"{emoji} {zone} Zone — {hex_name}",
        f"Risk Score: {score}/100 | Updated: {updated_str}",
        "Why we flagged this:",
    ]
    for r in reasons:
        lines.append(f"  • {r}")
    return "\n".join(lines)


# --- Quick test ---
if __name__ == "__main__":
    card = build_reason_card(
        zone="RED",
        score=78,
        crime_count=35,
        crime_severity=0.8,
        weather_score=0.5,
        weather_condition="Heavy Rain",
        time_detail={
            "time_score": 0.8,
            "hour": 23,
            "day_type": "weekday",
            "festival": None,
        },
        event_reason="Active flood alert nearby",
        event_delta=0.2,
        hex_name="Andheri East",
        updated_mins_ago=4,
    )

    print(card["display"])
    print("\nJSON reasons:", card["reasons"])