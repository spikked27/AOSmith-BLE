"""Downloadable diagnostics; identifiers and pairing material are excluded."""

from dataclasses import asdict

from homeassistant.const import __version__ as ha_version
from homeassistant.util import dt as dt_util

from .const import DOMAIN, VERSION


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    return {
        "integration_version": VERSION,
        "home_assistant_version": ha_version,
        "protocol_profile": "next_gen_heat_pump",
        "options": dict(entry.options),
        "host_clock": {"utc": dt_util.utcnow().isoformat(), "time_zone": hass.config.time_zone},
        "clock_sync": "Not implemented; clock candidate registers are read-only research",
        "tariff_programming": "Not implemented; selected tariff is cached only",
        "last_update_success": coordinator.last_update_success if coordinator else None,
        "state": asdict(coordinator.data) if coordinator and coordinator.data else None,
        "transport": coordinator.client.diagnostics() if coordinator else None,
        "redacted": ["address", "name", "pin", "pairing_identifier", "challenge", "auth_digest"],
    }
