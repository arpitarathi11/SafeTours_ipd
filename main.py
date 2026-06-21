# main.py
# Endpoints:
#   GET  /score                          → raw score for a lat/lng (debug/map use)
#   POST /update-location                → mobile app polls this; returns score + alert if zone changed
#   POST /register-token                 → store FCM/APNs push token for a user
#   POST /checkin-response               → user tapped the check-in notification
#   POST /register-emergency-contacts    → store emergency contacts for a user (Phase 5)
#   POST /cancel-sos                     → user cancels an SOS that fired by mistake (Phase 5)
#   GET  /timer-status/<user_id>         → debug only, remove in production

import h3
import json
import os
import time
import threading
from flask import Flask, request, jsonify
from weather_layer        import get_weather_score
from score_engine         import calculate_base_score
from event_layer          import check_active_events
from zone_tracker         import update_user_zone, get_user_state
from reason_card          import build_reason_card
from device_registry      import registry as device_registry
from push_sender          import send_checkin
from sos_log import append_sos
from checkin_tracker      import tracker as checkin_tracker
from inactivity_timer     import engine as timer_engine
from contact_registry     import registry as contact_registry   # Phase 5 — new file
from sos_handler          import trigger_sos, cancel_sos        # Phase 5 — new file
from db import init_db
init_db()

app = Flask(__name__)

H3_RESOLUTION     = 9
SOS_CANCEL_WINDOW = 30  # seconds the user has to cancel after SOS fires


# ----------------------------
# SOS state (in-memory + JSON log)
# ----------------------------
# { user_id: {"fired_at": epoch, "cancelled": bool, "payload": {...}} }
_sos_state: dict = {}
_sos_lock         = threading.Lock()
SOS_LOG_FILE      = "sos_log.json"


def _load_sos_log() -> list:
    try:
        with open(SOS_LOG_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _append_sos_log(entry: dict):
    """Append one SOS event to the local JSON paper trail."""
    log = _load_sos_log()
    log.append(entry)
    sos_id = append_sos(
           user_id=user_id,
           lat=state.get("lat"),
           lng=state.get("lng"),
           zone=state.get("zone"),
           score=state.get("score"),
       )



# ----------------------------
# Real SOS function (replaces _sos_stub)
# ----------------------------
def _handle_sos(user_id: str):
    """
    Called by inactivity_timer when check-ins are exhausted.
    1. Grabs last known location + zone from zone_tracker.
    2. Stores SOS state (for cancel window).
    3. Logs to sos_log.json.
    4. Calls sos_handler.trigger_sos → sends SMS/WhatsApp to contacts.
    """
    user_state = get_user_state(user_id)
    contacts   = contact_registry.get(user_id)

    payload = {
        "user_id":    user_id,
        "lat":        user_state.get("lat"),
        "lng":        user_state.get("lng"),
        "zone":       user_state.get("zone", "UNKNOWN"),
        "score":      user_state.get("score"),
        "fired_at":   time.time(),
        "cancelled":  False,
        "contacts":   [c["phone"] for c in contacts],
    }

    with _sos_lock:
        _sos_state[user_id] = payload

    _append_sos_log(payload)

    if not contacts:
        # No contacts registered — log and return; nothing to notify
        print(f"[SOS] {user_id} has no emergency contacts registered. SOS logged only.")
        return

    trigger_sos(
        user_id=user_id,
        contacts=contacts,
        lat=payload["lat"],
        lng=payload["lng"],
        zone=payload["zone"],
        score=payload["score"],
        fired_at=payload["fired_at"],
    )


# ----------------------------
# Wire Phase 5 on startup
# ----------------------------
timer_engine.configure(
    send_checkin_fn=send_checkin,
    get_device_fn=device_registry.get,
    sos_fn=_handle_sos,          # ← real SOS, not stub
    checkin_tracker=checkin_tracker,
)


# ----------------------------
# Load hex score data once
# ----------------------------
print("Loading hex score data...")
_HEX_FILE = "hex_scores_enriched.json" if os.path.exists("hex_scores_enriched.json") \
else "hex_scores.json"
with open(_HEX_FILE, "r") as f:
    hex_data_list = json.load(f)
HEX_LOOKUP = {item["hex_id"]: item for item in hex_data_list}

print(f"Loaded {len(HEX_LOOKUP)} hexes")


# ----------------------------
# Shared scoring logic
# ----------------------------
def score_hex(hex_id: str, lat: float, lng: float, solo: bool = False, now=None) -> dict:
    """
    Given a hex_id + lat/lng, return full scored result dict.
    Used by both endpoints.
    """
    import datetime
    if now is None:
       import pytz
       now = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))

    weather = get_weather_score(lat, lng)
    events  = check_active_events()

    if events["hard_cap"]:
        return {
            "hex_id":            hex_id,
            "score":             100,
            "zone":              "RED",
            "hard_cap":          True,
            "crime_count":       0,
            "crime_severity":    0.0,
            "weather_score":     weather["weather_score"],
            "weather_condition": weather["condition"],
            "event_reason":      events["reason"],
            "event_delta":       events["delta"],
            "time_detail":       {},
            "lat":               lat,
            "lng":               lng,
        }

    if hex_id in HEX_LOOKUP:
        hex_record     = HEX_LOOKUP[hex_id]
        crime_count    = hex_record["crime_count"]
        crime_severity = hex_record["crime_severity"]
        hex_lat        = hex_record["lat"]
        hex_lng        = hex_record["lng"]
    else:
        hex_record     = {"crime_count": 0, "crime_severity": 0.0, "infra_score": 0.5}
        crime_count    = 0
        crime_severity = 0.0
        hex_lat        = lat
        hex_lng        = lng

    combined_weather = min(1.0, weather["weather_score"] + events["delta"])

    result = calculate_base_score(
        crime_count    = crime_count,
        crime_severity = crime_severity,
        weather_score  = combined_weather,
        infra_score    = hex_record.get("infra_score", 0.5),
        solo_traveller = solo,
        now            = now,
    )

    return {
        "hex_id":            hex_id,
        "score":             result["score"],
        "zone":              result["zone"],
        "hard_cap":          False,
        "crime_count":       crime_count,
        "crime_severity":    crime_severity,
        "weather_score":     weather["weather_score"],
        "weather_condition": weather["condition"],
        "event_reason":      events["reason"],
        "event_delta":       events["delta"],
        "time_detail":       result["time_detail"],
        "breakdown":         result["breakdown"],
        "lat":               hex_lat,
        "lng":               hex_lng,
    }


# ----------------------------
# GET /score — debug / map tiles
# ----------------------------
@app.route("/score", methods=["GET"])
def get_score():
    """
    Returns raw score + reason card for a lat/lng.
    No user tracking. Used by the map renderer.

    Example: /score?lat=19.076&lng=72.877
    """
    try:
        lat = float(request.args.get("lat"))
        lng = float(request.args.get("lng"))
    except (TypeError, ValueError):
        return jsonify({"error": "lat and lng are required"}), 400

    hex_id = h3.latlng_to_cell(lat, lng, H3_RESOLUTION)
    data   = score_hex(hex_id, lat, lng)

    card = build_reason_card(
        zone=data["zone"],
        score=data["score"],
        crime_count=data["crime_count"],
        crime_severity=data["crime_severity"],
        weather_score=data["weather_score"],
        weather_condition=data["weather_condition"],
        time_detail=data["time_detail"],
        event_reason=data["event_reason"],
        event_delta=data["event_delta"],
    )

    return jsonify({**data, "reason_card": card})


# ----------------------------
# POST /update-location — mobile GPS poll
# ----------------------------
@app.route("/update-location", methods=["POST"])
def update_location():
    """
    Mobile app calls this every X seconds with user's GPS.
    Returns score + alert if zone has escalated.

    Body: { "user_id": "abc123", "lat": 19.076, "lng": 72.877, "solo": true }
    """
    body = request.get_json(silent=True) or {}

    user_id = body.get("user_id")
    lat     = body.get("lat")
    lng     = body.get("lng")
    solo    = body.get("solo", False)

    if not user_id or lat is None or lng is None:
        return jsonify({"error": "user_id, lat, and lng are required"}), 400

    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return jsonify({"error": "lat and lng must be numbers"}), 400

    hex_id = h3.latlng_to_cell(lat, lng, H3_RESOLUTION)
    data   = score_hex(hex_id, lat, lng)

    transition = update_user_zone(
        user_id=user_id,
        hex_id=hex_id,
        zone=data["zone"],
        score=data["score"],
    )

    # Reset inactivity timer on every location update
    timer_engine.reset(user_id, data["zone"])

    card = build_reason_card(
        zone=data["zone"],
        score=data["score"],
        crime_count=data["crime_count"],
        crime_severity=data["crime_severity"],
        weather_score=data["weather_score"],
        weather_condition=data["weather_condition"],
        time_detail=data["time_detail"],
        event_reason=data["event_reason"],
        event_delta=data["event_delta"],
        updated_mins_ago=0,
    )

    return jsonify({
        "hex_id":         data["hex_id"],
        "score":          data["score"],
        "zone":           data["zone"],
        "zone_changed":   transition["zone_changed"],
        "previous_zone":  transition["previous_zone"],
        "direction":      transition["direction"],
        "alert_required": transition["alert_required"],
        "reason_card":    card,
        "breakdown":      data.get("breakdown", {}),
        "lat":            data["lat"],
        "lng":            data["lng"],
    })


# ----------------------------
# POST /register-token — store push token
# ----------------------------
@app.route("/register-token", methods=["POST"])
def register_token():
    """
    Called by the app on launch or when FCM token refreshes.

    Body: { "user_id": "abc", "push_token": "...", "platform": "android"|"ios", "solo": true }
    """
    body = request.get_json(silent=True) or {}

    user_id    = body.get("user_id")
    push_token = body.get("push_token")
    platform   = body.get("platform", "android")
    solo       = body.get("solo", True)

    if not user_id or not push_token:
        return jsonify({"error": "user_id and push_token required"}), 400

    if platform not in ("android", "ios"):
        return jsonify({"error": "platform must be 'android' or 'ios'"}), 400

    device_registry.register(user_id, push_token, platform, solo)
    return jsonify({"status": "registered"}), 200


# ----------------------------
# POST /checkin-response — user confirmed they're safe
# ----------------------------
@app.route("/checkin-response", methods=["POST"])
def checkin_response():
    """
    Called by the app when the user taps the check-in notification.

    Body: { "user_id": "abc" }
    """
    body = request.get_json(silent=True) or {}

    user_id = body.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    reset = timer_engine.acknowledge_checkin(user_id)
    checkin_tracker.record_response(user_id)

    return jsonify({"status": "ok", "timer_reset": reset}), 200


# ----------------------------
# POST /register-emergency-contacts — Phase 5
# ----------------------------
@app.route("/register-emergency-contacts", methods=["POST"])
def register_emergency_contacts():
    """
    Store emergency contacts for a user.
    At least one contact is required.
    Replaces any previously stored contacts for this user.

    Body:
    {
        "user_id": "abc",
        "user_name": "Priya Sharma",
        "contacts": [
            { "name": "Rohit Sharma", "phone": "+919876543210" },
            { "name": "Anjali Mehta", "phone": "+919123456789" }
        ]
    }

    Phone numbers must be E.164 format (+country_code + number).
    """
    body = request.get_json(silent=True) or {}

    user_id   = body.get("user_id")
    user_name = body.get("user_name", "").strip()
    contacts  = body.get("contacts", [])

    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    if not contacts or not isinstance(contacts, list):
        return jsonify({"error": "contacts must be a non-empty list"}), 400

    # Validate each contact
    validated = []
    for i, c in enumerate(contacts):
        name  = c.get("name", "").strip()
        phone = c.get("phone", "").strip()

        if not name:
            return jsonify({"error": f"Contact {i+1}: name is required"}), 400

        if not phone.startswith("+") or not phone[1:].isdigit() or len(phone) < 8:
            return jsonify({
                "error": f"Contact {i+1}: phone must be E.164 format e.g. +919876543210"
            }), 400

        validated.append({"name": name, "phone": phone})

    contact_registry.register(user_id, user_name, validated)

    return jsonify({
        "status":          "registered",
        "user_id":         user_id,
        "contacts_stored": len(validated),
    }), 200


# ----------------------------
# POST /cancel-sos — Phase 5
# ----------------------------
@app.route("/cancel-sos", methods=["POST"])
def cancel_sos_endpoint():
    """
    User calls this if SOS fired by mistake.
    Only accepted within SOS_CANCEL_WINDOW seconds of SOS firing.
    Sends a cancellation notice to emergency contacts.

    Body: { "user_id": "abc" }
    """
    body = request.get_json(silent=True) or {}

    user_id = body.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    with _sos_lock:
        sos = _sos_state.get(user_id)

    if not sos:
        return jsonify({"error": "No active SOS found for this user"}), 404

    if sos.get("cancelled"):
        return jsonify({"error": "SOS already cancelled"}), 409

    elapsed = time.time() - sos["fired_at"]
    if elapsed > SOS_CANCEL_WINDOW:
        return jsonify({
            "error":           "Cancellation window expired",
            "window_seconds":  SOS_CANCEL_WINDOW,
            "elapsed_seconds": round(elapsed, 1),
        }), 410

    # Mark cancelled in memory and log
    with _sos_lock:
        _sos_state[user_id]["cancelled"] = True

    # Update log entry
    log = _load_sos_log()
    for entry in reversed(log):
        if entry["user_id"] == user_id and not entry.get("cancelled"):
            entry["cancelled"]    = True
            entry["cancelled_at"] = time.time()
            break
    with open(SOS_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)

    # Notify contacts that the SOS was a false alarm
    contacts = contact_registry.get(user_id)
    if contacts:
        cancel_sos(
            user_id=user_id,
            contacts=contacts,
            original_fired_at=sos["fired_at"],
        )

    return jsonify({
        "status":  "cancelled",
        "message": "Emergency contacts have been notified that you are safe.",
    }), 200


# ----------------------------
# GET /timer-status/<user_id> — debug only, remove in production
# ----------------------------
@app.route("/timer-status/<user_id>", methods=["GET"])
def timer_status(user_id):
    return jsonify(timer_engine.status(user_id)), 200


# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=5000)