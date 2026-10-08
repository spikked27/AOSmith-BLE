"""Durable clock write history; acceptance is separate from timing verification."""

import logging

from homeassistant.helpers.storage import Store

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)
ACCEPTED = {"readback_confirmed", "acknowledged"}


class ClockHistory:
    def __init__(self, hass, entry, client, local_now):
        self.local_now = local_now
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.clock")
        self.state = {}
        self.loaded = False

    async def async_load(self):
        if not self.loaded:
            saved = await self.store.async_load()
            self.state = saved if isinstance(saved, dict) else {}
            self.state.pop("automatic_setting_enabled", None)
            self.state.pop("next_check_at", None)
            self.state.pop("pending_reason", None)
            self.loaded = True

    def context(self, now):
        return {"time_zone": str(now.tzinfo), "utc_offset": int(now.utcoffset().total_seconds())}

    async def async_record_operation(self, operation, *, reason):
        """Persist the last explicit clock write; never infer clock health from readback."""
        if not operation or "requested_words" not in operation:
            return
        try:
            await self.async_load()
        except (OSError, ValueError) as err:
            LOGGER.warning("Could not load manual clock history: %s", err)
            return
        now = self.local_now()
        self.state.update(
            {
                "last_attempt_at": operation["time"],
                "last_reason": reason,
                "last_attempt_succeeded": operation.get("outcome") in ACCEPTED,
                "last_operation": dict(operation),
                "status": "write_accepted" if operation.get("outcome") in ACCEPTED else "write_failed",
            }
        )
        if operation.get("outcome") in ACCEPTED:
            self.state.update({"last_synced_at": operation["time"], "sync_context": self.context(now)})
            self.state.pop("error", None)
        try:
            await self.store.async_save(self.state)
        except (OSError, ValueError) as err:
            LOGGER.warning("Could not save manual clock history: %s", err)
