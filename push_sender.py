"""
push_sender.py
Sends FCM push notifications. APNs stub included for Phase 5+.

Requires: pip install requests
Env var:  FCM_SERVER_KEY  (Firebase legacy HTTP v1 key)
          For production, migrate to FCM HTTP v2 with OAuth2.
"""
import os
import logging
import requests

logger = logging.getLogger(__name__)

FCM_URL = "https://fcm.googleapis.com/fcm/send"
FCM_KEY = os.getenv("FCM_SERVER_KEY", "")

# Notification bodies per zone
CHECKIN_MESSAGES = {
    "YELLOW": {
        "title": "Safety check-in",
        "body": "Are you okay? Tap to confirm you're safe.",
    },
    "ORANGE": {
        "title": "Safety check-in — elevated area",
        "body": "You're in a higher-risk area. Tap to confirm you're safe.",
    },
    "RED": {
        "title": "⚠️ Safety check-in — high-risk area",
        "body": "Urgent: confirm you're safe or your emergency contacts will be alerted.",
    },
}


def send_checkin(push_token: str, platform: str, zone: str, user_id: str) -> bool:
    """
    Send a check-in push notification. Returns True on success.
    Fails silently and logs on error (never crash the caller).
    """
    if not push_token:
        logger.warning("send_checkin: no push token for user %s", user_id)
        return False

    payload = CHECKIN_MESSAGES.get(zone, CHECKIN_MESSAGES["YELLOW"])

    if platform == "android":
        return _send_fcm(push_token, payload, user_id, zone)
    elif platform == "ios":
        return _send_apns_stub(push_token, payload, user_id)
    else:
        logger.warning("send_checkin: unknown platform '%s' for user %s", platform, user_id)
        return False


def _send_fcm(token: str, payload: dict, user_id: str, zone: str) -> bool:
    if not FCM_KEY:
        logger.warning("FCM_SERVER_KEY not set — push skipped for user %s", user_id)
        return False

    body = {
        "to": token,
        "notification": {
            "title": payload["title"],
            "body": payload["body"],
            "sound": "default",
        },
        "data": {
            "type": "safety_checkin",
            "user_id": user_id,
            "zone": zone,
        },
        "priority": "high",
        "android": {"priority": "high"},
    }

    try:
        r = requests.post(
            FCM_URL,
            json=body,
            headers={
                "Authorization": f"key={FCM_KEY}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        if r.status_code == 200 and r.json().get("success") == 1:
            logger.info("FCM push sent to user %s (zone=%s)", user_id, zone)
            return True
        logger.warning("FCM push failed for user %s: %s", user_id, r.text)
        return False
    except Exception as e:
        logger.error("FCM push exception for user %s: %s", user_id, e)
        return False


def _send_apns_stub(token: str, payload: dict, user_id: str) -> bool:
    """
    APNs stub — wire up PyAPNs2 or httpx + JWT in Phase 5.
    Logs intent so iOS users aren't silently dropped.
    """
    logger.info(
        "APNs stub: would send '%s' to user %s (token=%s…)",
        payload["title"], user_id, token[:8],
    )
    return False  # Flip to True once wired