"""Downloadable diagnostics; identifiers and pairing material are excluded."""

from dataclasses import asdict

from homeassistant.const import __version__ as ha_version

from .const import DOMAIN


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    return {
        "integration_version": "0.1.1",
        "home_assistant_version": ha_version,
        "protocol_profile": "next_gen_heat_pump",
        "options": dict(entry.options),
        "last_update_success": coordinator.last_update_success if coordinator else None,
        "state": asdict(coordinator.data) if coordinator and coordinator.data else None,
        "transport": coordinator.client.diagnostics() if coordinator else None,
        "redacted": ["address", "name", "pin", "pairing_identifier", "challenge", "auth_digest"],
    }
