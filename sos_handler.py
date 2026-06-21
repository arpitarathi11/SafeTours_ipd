# sos_handler.py
# Sends SOS alerts and cancellation notices to emergency contacts.
#
# Primary:  Fast2SMS (good for India, cheaper than Twilio)
# Fallback: Twilio stub (log only) — wire real credentials to activate
#
# Set env vars before running:
#   $env:FAST2SMS_API_KEY = "your_key"          # Windows PS
#   export FAST2SMS_API_KEY="your_key"           # Linux/Mac
#
# Optional Twilio fallback:
#   $env:TWILIO_ACCOUNT_SID = "..."
#   $env:TWILIO_AUTH_TOKEN  = "..."
#   $env:TWILIO_FROM_NUMBER = "+1..."

import os
import time
import requests
from datetime import datetime, timezone


# ----------------------------
# Config
# ----------------------------
FAST2SMS_API_KEY   = os.environ.get("FAST2SMS_API_KEY", "")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "")


# ----------------------------
# Message builders
# ----------------------------
def _sos_message(user_name: str, lat, lng, zone: str, score, fired_at: float) -> str:
    timestamp = datetime.fromtimestamp(fired_at, tz=timezone.utc).strftime("%H:%M UTC")
    location  = f"https://maps.google.com/?q={lat},{lng}" if lat and lng else "unknown"
    return (
        f"SAFETY ALERT: {user_name} may need help.\n"
        f"Zone: {zone}  Score: {score}\n"
        f"Time: {timestamp}\n"
        f"Last location: {location}\n"
        f"If unreachable, call emergency services (112)."
    )


def _cancel_message(user_name: str, original_fired_at: float) -> str:
    timestamp = datetime.fromtimestamp(original_fired_at, tz=timezone.utc).strftime("%H:%M UTC")
    return (
        f"UPDATE: {user_name} is safe. "
        f"The safety alert sent at {timestamp} was a false alarm. No action needed."
    )


# ----------------------------
# Fast2SMS sender (India)
# ----------------------------
def _send_fast2sms(phone: str, message: str) -> bool:
    """
    Send SMS via Fast2SMS DLT route.
    phone: E.164 format (+91XXXXXXXXXX) — strips leading +91 for the API.
    Returns True on success, False on failure.
    """
    if not FAST2SMS_API_KEY:
        print(f"[SOS] Fast2SMS key not set. Would send to {phone}: {message[:60]}...")
        return False

    # Fast2SMS expects 10-digit Indian numbers
    number = phone.lstrip("+")
    if number.startswith("91") and len(number) == 12:
        number = number[2:]   # strip country code

    try:
        resp = requests.post(
            "https://www.fast2sms.com/dev/bulkV2",
            headers={"authorization": FAST2SMS_API_KEY},
            json={
                "route":   "q",          # quick/transactional route
                "message": message,
                "numbers": number,
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("return"):
            print(f"[SOS] Fast2SMS sent to {phone}")
            return True
        else:
            print(f"[SOS] Fast2SMS error for {phone}: {data}")
            return False
    except Exception as e:
        print(f"[SOS] Fast2SMS exception for {phone}: {e}")
        return False


# ----------------------------
# Twilio fallback (stub — activate with real credentials)
# ----------------------------
def _send_twilio(phone: str, message: str) -> bool:
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER]):
        print(f"[SOS] Twilio not configured. Would send to {phone}: {message[:60]}...")
        return False

    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            body=message,
            from_=TWILIO_FROM_NUMBER,
            to=phone,
        )
        print(f"[SOS] Twilio sent to {phone}, SID={msg.sid}")
        return True
    except Exception as e:
        print(f"[SOS] Twilio exception for {phone}: {e}")
        return False


# ----------------------------
# Unified sender — Fast2SMS first, Twilio fallback
# ----------------------------
def _send_sms(phone: str, message: str) -> bool:
    if _send_fast2sms(phone, message):
        return True
    return _send_twilio(phone, message)


# ----------------------------
# Public API
# ----------------------------
def trigger_sos(
    user_id:   str,
    contacts:  list,
    lat,
    lng,
    zone:      str,
    score,
    fired_at:  float,
):
    """
    Send SOS alert to all emergency contacts.

    contacts: [{ "name": str, "phone": str }, ...]
    Called by _handle_sos() in main.py.
    """
    from contact_registry import registry as contact_registry
    user_name = contact_registry.get_user_name(user_id)

    message = _sos_message(user_name, lat, lng, zone, score, fired_at)

    print(f"[SOS] Triggering SOS for {user_id} ({user_name}) → {len(contacts)} contact(s)")

    for contact in contacts:
        phone = contact.get("phone", "")
        name  = contact.get("name", "contact")
        ok    = _send_sms(phone, message)
        if not ok:
            print(f"[SOS] Failed to reach {name} at {phone}")


def cancel_sos(
    user_id:          str,
    contacts:         list,
    original_fired_at: float,
):
    """
    Notify contacts that the SOS was a false alarm.
    Called by /cancel-sos endpoint in main.py.
    """
    from contact_registry import registry as contact_registry
    user_name = contact_registry.get_user_name(user_id)

    message = _cancel_message(user_name, original_fired_at)

    print(f"[SOS] Sending cancellation for {user_id} ({user_name}) → {len(contacts)} contact(s)")

    for contact in contacts:
        phone = contact.get("phone", "")
        name  = contact.get("name", "contact")
        ok    = _send_sms(phone, message)
        if not ok:
            print(f"[SOS] Failed to send cancellation to {name} at {phone}")