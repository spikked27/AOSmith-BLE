"""Local AO Smith BLE integration."""

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform

from .const import DOMAIN
from .coordinator import HeaterCoordinator

PLATFORMS = [Platform.WATER_HEATER, Platform.SENSOR, Platform.BUTTON]


async def async_setup_entry(hass, entry):
    coordinator = HeaterCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async def stop(_event):
        await coordinator.client.disconnect()

    async def reload_entry(hass, entry):
        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop))
    entry.async_on_unload(entry.add_update_listener(reload_entry))
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await coordinator.client.disconnect()
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise
    return True


async def async_unload_entry(hass, entry):
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.client.disconnect()
    return unloaded
