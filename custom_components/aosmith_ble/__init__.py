"""Local AO Smith BLE integration."""

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform

from .const import DOMAIN
from .coordinator import HeaterCoordinator

PLATFORMS = [
    Platform.WATER_HEATER,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
]


async def async_setup(hass, config):
    from .services import async_register_services

    async_register_services(hass)
    return True


async def async_setup_entry(hass, entry):
    from homeassistant.helpers import entity_registry as er

    # Retire only this integration's demand-response entities; preserve history.
    registry = er.async_get(hass)
    retired = {"utility_override", "advanced_load", "utility_enrollment", "cta_present"}
    retired |= {key + "_control" for key in retired}
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.platform == DOMAIN and any(entity.unique_id.endswith("_" + key) for key in retired):
            if entity.disabled_by is None:
                registry.async_update_entity(
                    entity.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION
                )
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
