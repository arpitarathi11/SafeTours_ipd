"""
inactivity_timer.py
Zone-aware inactivity timer engine.

One threading.Timer per active user. Resets on every /update-location call.
GREEN zone: no timer (monitoring suspended).
YELLOW/ORANGE/RED: fires check-ins, then escalates to SOS stub.

Thread safety: all timer state behind a lock.
"""
import threading
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Zone → (interval_seconds, max_checkin_attempts)
ZONE_CONFIG = {
    "GREEN":  (None, 0),          # No monitoring
    "YELLOW": (45 * 60, 2),       # 45 min, 2 check-ins
    "ORANGE": (20 * 60, 2),       # 20 min, 2 check-ins
    "RED":    (10 * 60, 1),       # 10 min, 1 check-in → SOS
}


class UserTimer:
    """Holds the live timer + metadata for one user."""
    def __init__(self, user_id: str, zone: str, timer: Optional[threading.Timer]):
        self.user_id = user_id
        self.zone = zone
        self.timer = timer
        self.checkins_sent = 0
        self.max_checkins: int = ZONE_CONFIG.get(zone, (None, 0))[1]
        self.last_reset = time.time()


class InactivityTimerEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._timers: dict = {}   # user_id → UserTimer

        # Injected at startup to avoid circular imports
        self._send_checkin_fn = None     # push_sender.send_checkin
        self._get_device_fn = None       # device_registry.registry.get
        self._sos_fn = None              # Phase 5 stub
        self._checkin_tracker = None     # checkin_tracker.tracker

    def configure(self, send_checkin_fn, get_device_fn, sos_fn, checkin_tracker):
        self._send_checkin_fn = send_checkin_fn
        self._get_device_fn = get_device_fn
        self._sos_fn = sos_fn
        self._checkin_tracker = checkin_tracker

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def reset(self, user_id: str, zone: str):
        """
        Called on every /update-location. Cancels any existing timer and
        starts a fresh one appropriate for the zone. GREEN = no timer.
        """
        with self._lock:
            self._cancel_existing(user_id)

            interval, max_checkins = ZONE_CONFIG.get(zone, (None, 0))
            if interval is None:
                logger.debug("Timer reset for %s: GREEN zone, no monitoring", user_id)
                self._timers.pop(user_id, None)
                return

            t = threading.Timer(interval, self._timer_fired, args=[user_id])
            t.daemon = True
            t.start()

            ut = UserTimer(user_id=user_id, zone=zone, timer=t)
            ut.max_checkins = max_checkins
            self._timers[user_id] = ut
            logger.debug(
                "Timer set for %s: zone=%s interval=%ds max_checkins=%d",
                user_id, zone, interval, max_checkins,
            )

        # Clear any pending check-in state from previous session
        if self._checkin_tracker:
            self._checkin_tracker.clear(user_id)

    def cancel(self, user_id: str):
        """Explicitly cancel (e.g. user logs out)."""
        with self._lock:
            self._cancel_existing(user_id)
            self._timers.pop(user_id, None)

    def acknowledge_checkin(self, user_id: str) -> bool:
        """
        Called by /checkin-response. Records response and resets the timer
        using the user's current zone. Returns False if user not tracked.
        """
        if self._checkin_tracker:
            self._checkin_tracker.record_response(user_id)

        with self._lock:
            ut = self._timers.get(user_id)
            if not ut:
                return False
            zone = ut.zone

        # Full reset — user proved they're active
        self.reset(user_id, zone)
        logger.info("Checkin acknowledged for %s, timer reset", user_id)
        return True

    def status(self, user_id: str) -> dict:
        with self._lock:
            ut = self._timers.get(user_id)
            if not ut:
                return {"monitoring": False}
            interval = ZONE_CONFIG[ut.zone][0]
            elapsed = time.time() - ut.last_reset
            return {
                "monitoring": True,
                "zone": ut.zone,
                "checkins_sent": ut.checkins_sent,
                "max_checkins": ut.max_checkins,
                "seconds_until_next_fire": max(0, interval - elapsed) if interval else None,
            }

    # ------------------------------------------------------------------ #
    #  Internal                                                            #
    # ------------------------------------------------------------------ #

    def _cancel_existing(self, user_id: str):
        """Must be called with self._lock held."""
        ut = self._timers.get(user_id)
        if ut and ut.timer:
            ut.timer.cancel()

    def _timer_fired(self, user_id: str):
        """
        Runs in a daemon thread when the timer expires.
        Decides: send another check-in, or escalate to SOS.
        """
        with self._lock:
            ut = self._timers.get(user_id)
            if not ut:
                return  # Race: timer cancelled before it fired
            zone = ut.zone
            ut.checkins_sent += 1
            checkins_sent = ut.checkins_sent
            max_checkins = ut.max_checkins

        logger.info(
            "Timer fired for user %s (zone=%s, attempt %d/%d)",
            user_id, zone, checkins_sent, max_checkins,
        )

        device = self._get_device_fn(user_id) if self._get_device_fn else None

        if checkins_sent == 1 and self._checkin_tracker:
            self._checkin_tracker.start_checkin(user_id, zone)
        elif self._checkin_tracker:
            self._checkin_tracker.record_attempt(user_id)

        # Send the push notification
        if device and self._send_checkin_fn:
            self._send_checkin_fn(
                push_token=device.push_token,
                platform=device.platform,
                zone=zone,
                user_id=user_id,
            )
        else:
            logger.warning("No device registered for user %s — cannot send push", user_id)

        # Check if we've exhausted attempts
        if checkins_sent >= max_checkins:
            # Give a short grace window for the response to arrive
            grace = threading.Timer(60, self._check_sos, args=[user_id, zone])
            grace.daemon = True
            grace.start()
        else:
            # Schedule the next check-in at the same zone interval
            interval = ZONE_CONFIG[zone][0]
            with self._lock:
                ut = self._timers.get(user_id)
                if ut:
                    t = threading.Timer(interval, self._timer_fired, args=[user_id])
                    t.daemon = True
                    t.start()
                    ut.timer = t
                    ut.last_reset = time.time()

    def _check_sos(self, user_id: str, zone: str):
        """
        Called after the grace window. If the user still hasn't responded,
        hand off to the SOS trigger (Phase 5).
        """
        if self._checkin_tracker and self._checkin_tracker.should_sos(user_id):
            logger.warning(
                "SOS threshold reached for user %s (zone=%s) — triggering SOS stub",
                user_id, zone,
            )
            if self._sos_fn:
                self._sos_fn(user_id, zone)
            else:
                logger.warning("SOS fn not configured — Phase 5 not yet wired")
        else:
            logger.info(
                "Grace window passed for user %s — response received, no SOS", user_id
            )


# Module-level singleton
engine = InactivityTimerEngine()


# Phase 5 SOS stub — replace with real implementation in next phase
def _sos_stub(user_id: str, zone: str):
    logger.critical(
        "SOS STUB: Would alert emergency contacts for user %s (zone=%s). "
        "Wire up Phase 5 here.", user_id, zone,
    )