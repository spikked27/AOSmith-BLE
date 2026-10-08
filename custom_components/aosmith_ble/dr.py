"""Opt-in, bounded read-only DR investigations. Raw values are not decoded DR levels."""

import asyncio
from contextlib import suppress
from datetime import timedelta
from time import monotonic

from homeassistant.components import persistent_notification
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store

from .const import DOMAIN

HISTORY_LIMIT = 400
SAMPLE_INTERVAL = 60


def changes_since(previous, current):
    """Compare successful reads only; errors must never look like a changed value."""
    changes = {}
    for address, row in current.get("registers", {}).items():
        before = previous.get("registers", {}).get(address, {})
        if before.get("raw") is not None and row.get("raw") is not None and before["raw"] != row["raw"]:
            changes[address] = {"before": before["raw"], "after": row["raw"], "name": row["name"]}
    return changes


class DRMonitor:
    """One explicit session, no resume on startup, persistent bounded capture history."""

    def __init__(self, hass, coordinator):
        self.coordinator = coordinator
        self.hass = hass
        self.store = Store(self.hass, 1, f"{DOMAIN}.{coordinator.entry.entry_id}.dr")
        self.data = {"status": "Idle", "captures": [], "active_dr_level": None}
        self.loaded = False
        self.task = None

    async def async_load(self):
        if self.loaded:
            return
        saved = await self.store.async_load()
        if isinstance(saved, dict):
            self.data = saved
            self.data["captures"] = self.data.get("captures", [])[-HISTORY_LIMIT:]
            if self.data.get("status") == "Monitoring":
                self.data["status"] = "Interrupted by restart"
                await self.store.async_save(self.data)
        self.data["active_dr_level"] = None
        self.data["interpretation"] = "Raw status investigation; no verified active DR register"
        self.loaded = True

    async def async_capture(self, *, source="manual", deadline=None):
        coordinator = self.coordinator
        async with coordinator.command_lock:
            if deadline is not None and monotonic() >= deadline:
                return None
            await self.async_load()
            capture = await coordinator.client.inspect_dr_status()
            capture.update(
                {
                    "source": source,
                    "host_local_time": coordinator.local_now().isoformat(),
                    "time_zone": self.hass.config.time_zone,
                    "tariff_preference": coordinator.tariff_preference,
                    "tariff_applied_at": (coordinator.tariff_state or {}).get("applied_at"),
                    "last_clock_operation": coordinator.clock.state.get("last_operation"),
                }
            )
            history = self.data["captures"]
            capture["changes_since_previous"] = changes_since(history[-1] if history else {}, capture)
            capture["compared_to"] = history[-1]["started_at"] if history else None
            history.append(capture)
            self.data["captures"] = history[-HISTORY_LIMIT:]
            self.data["last_capture_at"] = capture["time"]
            self.data["last_capture_complete"] = capture["complete"]
            self.data["retained_captures"] = len(self.data["captures"])
            if source == "monitor":
                self.data["session_captures"] += 1
                if capture["complete"]:
                    self.data.pop("last_read_error", None)
                else:
                    self.data["last_read_error"] = capture.get("error", "One or more registers rejected")
            await self.store.async_save(self.data)
            coordinator.async_update_listeners()
        return capture

    async def async_start(self, duration_minutes=180):
        if type(duration_minutes) is not int or not 1 <= duration_minutes <= 360:
            raise HomeAssistantError("Choose a monitoring duration from 1 to 360 minutes")
        async with self.coordinator.command_lock:
            if self.task and not self.task.done():
                raise HomeAssistantError("DR monitoring is already running")
            await self.async_load()
            now = self.coordinator.local_now()
            self.data.update(
                {
                    "status": "Monitoring",
                    "started_at": now.isoformat(),
                    "ends_at": (now + timedelta(minutes=duration_minutes)).isoformat(),
                    "interval_seconds": SAMPLE_INTERVAL,
                    "session_captures": 0,
                }
            )
            self.data.pop("error", None)
            self.data.pop("stopped_at", None)
            await self.store.async_save(self.data)
            self.task = self.coordinator.entry.async_create_background_task(
                self.hass, self._run(duration_minutes), "aosmith_dr_monitor", eager_start=False
            )
            self.coordinator.async_update_listeners()

    async def _run(self, duration_minutes):
        deadline = monotonic() + duration_minutes * 60
        try:
            while monotonic() < deadline:
                started = monotonic()
                # Failed reads stay in history; the next interval can reconnect.
                await self.async_capture(source="monitor", deadline=deadline)
                remaining = deadline - monotonic()
                if remaining > 0:
                    await asyncio.sleep(min(remaining, max(1, SAMPLE_INTERVAL - (monotonic() - started))))
            self.data["status"] = "Complete"
        except asyncio.CancelledError:
            self.data["status"] = "Stopped"
            raise
        except Exception as err:
            # Do not persist backend exceptions that may contain Bluetooth identifiers.
            self.data.update({"status": "Failed", "error": type(err).__name__})
        finally:
            self.data["stopped_at"] = self.coordinator.local_now().isoformat()
            await self.store.async_save(self.data)
            self.coordinator.async_update_listeners()
            if self.data["status"] in ("Complete", "Failed"):
                persistent_notification.async_create(
                    self.hass,
                    f"DR monitoring: {self.data['status']}. Download integration diagnostics to review "
                    "timestamped raw readings and changes. Active DR levels remain unverified.",
                    title="AO Smith DR monitoring finished",
                    notification_id=f"{DOMAIN}_{self.coordinator.entry.entry_id}_dr",
                )

    async def async_stop(self):
        if self.task and not self.task.done():
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
        # Covers cancellation before the task first entered _run.
        if self.data["status"] == "Monitoring":
            self.data["status"] = "Stopped"
            self.data["stopped_at"] = self.coordinator.local_now().isoformat()
            await self.store.async_save(self.data)
        self.coordinator.async_update_listeners()
