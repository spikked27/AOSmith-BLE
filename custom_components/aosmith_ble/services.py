"""Explicit duration action with per-heater targeting and schema validation."""

import voluptuous as vol
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, MODE
from .protocol import encode_timed_mode


@callback
def async_register_services(hass):
    async def timed_mode(call):
        coordinator = hass.data.get(DOMAIN, {}).get(call.data["config_entry_id"])
        if coordinator is None:
            raise HomeAssistantError("Select a loaded AO Smith Local BLE integration entry")
        try:
            value = encode_timed_mode(call.data["mode"], call.data["days"])
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_set_value(MODE, value)

    hass.services.async_register(
        DOMAIN,
        "set_timed_mode",
        timed_mode,
        schema=vol.Schema(
            {
                vol.Required("config_entry_id"): cv.string,
                vol.Required("mode"): vol.In(["Electric", "Vacation", "Guest"]),
                vol.Required("days"): vol.All(int, vol.Range(min=1, max=100)),
            }
        ),
    )
