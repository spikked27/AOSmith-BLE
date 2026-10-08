"""Control the bounded, transition-driven clock correction policy."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .entity import HeaterEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([AutomaticClockCorrection(hass.data[DOMAIN][entry.entry_id])])


class AutomaticClockCorrection(HeaterEntity, SwitchEntity):
    _attr_name = "Automatic clock correction"
    _attr_icon = "mdi:clock-sync-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator):
        super().__init__(coordinator, "automatic_clock_correction")

    @property
    def available(self):
        return True

    @property
    def is_on(self):
        return self.coordinator.clock_guard.automatic

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_set_automatic_clock(True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_set_automatic_clock(False)
