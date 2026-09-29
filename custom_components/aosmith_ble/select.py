"""Hot Water Plus is offered only when explicitly enabled for a supported model."""

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, HOT_WATER_PLUS
from .entity import HeaterEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.options.get("enable_hot_water_plus", False):
        async_add_entities([HotWaterPlus(hass.data[DOMAIN][entry.entry_id])])


class HotWaterPlus(HeaterEntity, SelectEntity):
    _attr_name = "Hot Water Plus"
    _attr_options = ["Off", "Level 1", "Level 2", "Level 3"]
    _attr_icon = "mdi:water-plus"

    def __init__(self, coordinator):
        super().__init__(coordinator, "hot_water_plus")

    @property
    def available(self):
        return super().available and self.coordinator.data.registers.get("hot_water_plus") in range(4)

    @property
    def current_option(self):
        value = self.coordinator.data.registers.get("hot_water_plus")
        return self.options[value] if value in range(4) else None

    async def async_select_option(self, option):
        if option not in self.options or not self.available:
            raise HomeAssistantError("Hot Water Plus is not available on this heater")
        if self.coordinator.data.mode not in (1, 4, 5):
            raise HomeAssistantError("Hot Water Plus requires Electric, Hybrid or Heat pump mode")
        await self.coordinator.async_set_value(HOT_WATER_PLUS, self.options.index(option))
