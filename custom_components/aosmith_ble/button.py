"""Explicit manual clock synchronization."""

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .entity import HeaterEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ClockButton(coordinator)])


class ClockButton(HeaterEntity, ButtonEntity):
    _attr_name = "Synchronize clock"
    _attr_icon = "mdi:clock-check-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator):
        super().__init__(coordinator, "set_clock")

    async def async_press(self):
        await self.coordinator.async_set_clock()
