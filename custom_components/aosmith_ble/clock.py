"""Automatic local-clock maintenance with bounded, persistent correction attempts."""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import monotonic

from bleak.exc import BleakError
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .protocol import ProtocolError, decode_clock

LOGGER = logging.getLogger(__name__)
CHECK_INTERVAL = 15 * 60
RETRY_INTERVAL = 60 * 60
MIN_SYNC_INTERVAL = 5 * 60
REFRESH_INTERVAL = 24 * 60 * 60
TOLERANCE = timedelta(minutes=2)
ACCEPTED = {"readback_confirmed", "acknowledged"}


def _saved_state(path):
    return json.loads(Path(path).read_text())["data"]


def elapsed(now, value):
    """Compare absolute instants across DST; a backwards host-clock jump resets age."""
    try:
        previous = datetime.fromisoformat(value)
        if previous.tzinfo is None:
            return None
        age = (now.astimezone(timezone.utc) - previous.astimezone(timezone.utc)).total_seconds()
        return age if age >= 0 else None
    except (TypeError, ValueError):
        return None


def correction_reason(words, now, state, context, *, clock_unset=False):
    """Compare only fields the device exposes; zero minutes are ambiguous on HPS10."""
    if clock_unset:
        return "heater_clock_unset"
    decoded = decode_clock(words)
    if decoded is None:
        return "invalid_clock"
    device = datetime.fromisoformat(decoded)
    expected = now.replace(tzinfo=None, second=0, microsecond=0)
    if state.get("sync_context") is not None and state["sync_context"] != context:
        return "timezone_or_dst_changed"
    if device.minute:
        return "clock_drift" if abs(device - expected) > TOLERANCE else None
    # The real device can mask minutes to zero. Treat it as an hour-wide interval,
    # allowing a short boundary grace period, rather than diagnosing 59 minutes of drift.
    if not device - TOLERANCE <= expected < device + timedelta(hours=1) + TOLERANCE:
        return "date_or_hour_mismatch"
    age = elapsed(now, state.get("last_synced_at"))
    if age is None or age >= REFRESH_INTERVAL:
        return "daily_refresh_partial_readback"
    return None


class ClockMaintenance:
    """Called under the coordinator command lock, never alongside a tariff upload."""

    def __init__(self, hass, entry, client, local_now):
        self.hass = hass
        self.client = client
        self.local_now = local_now
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.clock")
        self.state = {}
        self.loaded = False
        self.next_check = 0.0
        self.checked_context = None
        self.last_fault = None

    async def async_load(self):
        if not self.loaded:
            saved = await self.store.async_load()
            self.state = saved if isinstance(saved, dict) else {}
            self.loaded = True

    def context(self, now):
        return {"time_zone": self.hass.config.time_zone, "utc_offset": int(now.utcoffset().total_seconds())}

    async def async_record_operation(self, operation, *, reason):
        """Include manual and tariff clock writes in the maintenance history."""
        if not operation or "requested_words" not in operation:
            return
        try:
            await self.async_load()
        except (OSError, ValueError) as err:
            LOGGER.warning("Could not load clock maintenance history: %s", err)
            return
        now = self.local_now()
        self.state.update(
            {
                "last_attempt_at": operation["time"],
                "last_reason": reason,
                "last_attempt_succeeded": operation.get("outcome") in ACCEPTED,
                "last_operation": dict(operation),
                "status": "synchronized" if operation.get("outcome") in ACCEPTED else "sync_failed",
            }
        )
        if operation.get("outcome") in ACCEPTED:
            self.state.update({"last_synced_at": operation["time"], "sync_context": self.context(now)})
            self.state.pop("error", None)
        try:
            await self.store.async_save(self.state)
        except (OSError, ValueError) as err:
            LOGGER.warning("Could not save clock maintenance history: %s", err)

    async def async_check(self, fault, *, force=False):
        """Read on startup/recovery and every 15 minutes; clock failures leave controls usable."""
        now = self.local_now()
        context = self.context(now)
        if (
            not force
            and monotonic() < self.next_check
            and self.checked_context == context
            and not (fault == 42 and self.last_fault != 42)
        ):
            return
        self.next_check = monotonic() + CHECK_INTERVAL
        self.checked_context = context
        self.last_fault = fault
        try:
            await self.async_load()
            self.state["last_checked_at"] = now.isoformat()
            words = await self.client.read_clock()
            now = self.local_now()  # Do not compare against a timestamp from before BLE I/O.
            context = self.context(now)
            self.state.update(
                {
                    "observed_words": list(words),
                    "observed_local_time": decode_clock(words),
                    "readback_scope": "full" if words[0] >> 8 else "date_and_hour",
                    "rtc_running_verified": False,
                }
            )
            reason = correction_reason(words, now, self.state, context, clock_unset=fault == 42)
            if reason is None:
                self.state["status"] = "checked"
                self.state.pop("error", None)
                self.state.pop("pending_reason", None)
                return
            age = elapsed(now, self.state.get("last_attempt_at"))
            cooldown = MIN_SYNC_INTERVAL if self.state.get("last_attempt_succeeded") else RETRY_INTERVAL
            if age is not None and age < cooldown:
                self.state.update({"status": "correction_deferred", "pending_reason": reason})
                return
            self.state.pop("pending_reason", None)
            self.state.update(
                {
                    "last_attempt_at": now.isoformat(),
                    "last_reason": reason,
                    "last_attempt_succeeded": False,
                    "status": "synchronizing",
                }
            )
            # Save before transmission, including before a crash or cancelled request.
            # HA Store can log an error without raising, so verify the durable retry limit.
            await self.store.async_save(self.state)
            saved = await self.hass.async_add_executor_job(_saved_state, self.store.path)
            if saved != self.state:
                raise OSError("Could not persist clock retry limit; no automatic write sent")
            LOGGER.info("Synchronizing heater clock: %s", reason)
            previous = self.client.clock_operation
            try:
                await self.client.set_clock(self.local_now)
            finally:
                if self.client.clock_operation is not previous:
                    await self.async_record_operation(self.client.clock_operation, reason=reason)
        except (BleakError, TimeoutError, ProtocolError, OSError, ValueError, KeyError) as err:
            self.state.update({"status": "check_failed", "error": str(err) or type(err).__name__})
            LOGGER.warning("Heater clock maintenance failed; normal controls remain available: %s", err)
        finally:
            if self.loaded:
                try:
                    await self.store.async_save(self.state)
                except (OSError, ValueError) as err:
                    self.state["error"] = "Could not save clock maintenance history"
                    LOGGER.warning("Could not save clock maintenance history: %s", err)
