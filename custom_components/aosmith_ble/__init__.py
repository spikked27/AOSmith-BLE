"""Local AO Smith BLE integration."""

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform

from .const import DOMAIN, clean_options
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

    # Keep only supported user settings; pairing credentials remain in entry.data.
    options = clean_options(entry.options)
    if options != entry.options:
        hass.config_entries.async_update_entry(entry, options=options)

    # Retire only this integration's removed entities; preserve history.
    registry = er.async_get(hass)
    retired = {"utility_override", "advanced_load", "utility_enrollment", "cta_present"}
    retired |= {key + "_control" for key in retired}
    retired |= {
        "tariff",
        "fault",
        "target_temperature",
        "maximum_setpoint",
        "remote_setpoint",
        "vacation_days",
        "guest_days",
        "electric_days",
        "mode_duration",
    }
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.platform == DOMAIN and any(entity.unique_id.endswith("_" + key) for key in retired):
            if entity.disabled_by is None:
                registry.async_update_entity(
                    entity.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION
                )
    coordinator = HeaterCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except BaseException:
        await coordinator.client.disconnect()
        raise
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


async def async_migrate_entry(hass, entry):
    """Retire the draft's default-enabled debug controls once, not on each reload."""
    from homeassistant.helpers import entity_registry as er

    if entry.version > 1:
        return False
    if entry.minor_version < 2:
        registry = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
            if (
                entity.platform == DOMAIN
                and entity.domain == "button"
                and any(entity.unique_id.endswith("_" + key) for key in ("refresh", "reconnect", "inspect"))
                and entity.disabled_by is None
            ):
                registry.async_update_entity(
                    entity.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION
                )
        hass.config_entries.async_update_entry(entry, minor_version=2, options=clean_options(entry.options))
    return True
