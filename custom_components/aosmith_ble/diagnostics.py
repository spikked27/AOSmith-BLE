"""Downloadable diagnostics; identifiers and pairing material are excluded."""

from dataclasses import asdict

from homeassistant.const import __version__ as ha_version
from homeassistant.util import dt as dt_util

from .const import DOMAIN, VERSION, clean_options
from .faults import fault_details


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    return {
        "integration_version": VERSION,
        "downloaded_version": getattr(coordinator, "installed_version", None),
        "diagnostic_read_status": getattr(coordinator, "diagnostic_status", None),
        "home_assistant_version": ha_version,
        "protocol_profile": "next_gen_heat_pump",
        "options": clean_options(entry.options),
        "clock_maintenance": getattr(getattr(coordinator, "clock", None), "state", None),
        "host_clock": {"utc": dt_util.utcnow().isoformat(), "time_zone": hass.config.time_zone},
        "clock_sync": "Automatic local-time maintenance at 26:3–4; see clock_maintenance and clock_operation for full/partial readback; RTC ticking and firmware DST behavior are not verified",
        "heater_error": fault_details(coordinator.data.fault)
        if coordinator and coordinator.data and coordinator.last_update_success
        else None,
        "last_update_success": coordinator.last_update_success if coordinator else None,
        "state": asdict(coordinator.data) if coordinator and coordinator.data else None,
        "transport": coordinator.client.diagnostics() if coordinator else None,
        "energy_preference_original": getattr(coordinator, "preference_backup", None),
        "tariff_state": getattr(coordinator, "tariff_state", None),
        "redacted": ["address", "name", "pin", "pairing_identifier", "challenge", "auth_digest"],
    }
