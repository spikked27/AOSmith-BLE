"""Diagnostic buttons for read-only refresh and reconnect experiments."""

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .const import CONF_ENERGY_PREFERENCE, DOMAIN
from .entity import HeaterEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            DebugButton(coordinator, "refresh"),
            DebugButton(coordinator, "reconnect"),
            DebugButton(coordinator, "inspect"),
        ]
    )
    if entry.options.get(CONF_ENERGY_PREFERENCE, False):
        async_add_entities([RestoreEnergyPreference(coordinator)])


class RestoreEnergyPreference(HeaterEntity, ButtonEntity):
    _attr_name = "Restore original energy preference"
    _attr_icon = "mdi:backup-restore"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator):
        super().__init__(coordinator, "restore_energy_preference")

    @property
    def available(self):
        return bool(self.coordinator.preference_backup)

    async def async_press(self):
        await self.coordinator.async_test_energy_preference(restore=True)


class DebugButton(HeaterEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, action):
        super().__init__(coordinator, action)
        self.action = action
        self._attr_name = {
            "refresh": "Refresh readings",
            "reconnect": "Reconnect Bluetooth",
            "inspect": "Inspect extended registers",
        }[action]
        self._attr_icon = "mdi:refresh" if action == "refresh" else "mdi:bluetooth-connect"

    @property
    def available(self):
        # Recovery actions must remain usable after a failed poll/disconnect.
        return True

    async def async_press(self):
        if self.action == "inspect":
            await self.coordinator.async_inspect_registers()
            return
        if self.action == "reconnect":
            async with self.coordinator.command_lock:
                await self.coordinator.client.disconnect()
        await self.coordinator.async_request_refresh()
