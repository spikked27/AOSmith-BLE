"""Diagnostic buttons for read-only refresh and reconnect experiments."""

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .entity import HeaterEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DebugButton(coordinator, "refresh"), DebugButton(coordinator, "reconnect")])


class DebugButton(HeaterEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, action):
        super().__init__(coordinator, action)
        self.action = action
        self._attr_name = "Refresh readings" if action == "refresh" else "Reconnect Bluetooth"
        self._attr_icon = "mdi:refresh" if action == "refresh" else "mdi:bluetooth-connect"

    async def async_press(self):
        if self.action == "reconnect":
            async with self.coordinator.command_lock:
                await self.coordinator.client.disconnect()
        await self.coordinator.async_request_refresh()
