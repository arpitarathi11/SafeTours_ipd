"""
push_sender.py
Sends FCM push notifications via Firebase Admin SDK (HTTP v1).
APNs stub included for Phase 5+.

Requires: pip install firebase-admin
Env var:  FIREBASE_CRED_PATH  (path to serviceAccountKey.json, defaults below)
"""
import os
import logging

import firebase_admin
from firebase_admin import credentials, messaging

logger = logging.getLogger(__name__)

CRED_PATH = os.getenv("FIREBASE_CRED_PATH", "serviceAccountKey.json")

# Initialize the Firebase app once, at import time.
if not firebase_admin._apps:
    cred = credentials.Certificate(CRED_PATH)
    firebase_admin.initialize_app(cred)

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
    message = messaging.Message(
        token=token,
        notification=messaging.Notification(
            title=payload["title"],
            body=payload["body"],
        ),
        data={
            "type": "safety_checkin",
            "user_id": user_id,
            "zone": zone,
        },
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(sound="default"),
        ),
    )

    try:
        response = messaging.send(message)
        logger.info("FCM push sent to user %s (zone=%s, id=%s)", user_id, zone, response)
        return True
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