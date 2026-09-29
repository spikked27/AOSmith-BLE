"""Opt-in APK-derived utility flags; these do not enroll a utility account."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, OPTIONAL_REGISTERS
from .entity import HeaterEntity

SWITCHES = {
    "utility_override": ("Pause utility demand response", 1),
    "advanced_load": ("Advanced load-up", 0xA5),
    "utility_enrollment": ("Utility enrollment device flag", 1),
}


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.options.get("enable_utility_controls", False):
        async_add_entities([UtilitySwitch(hass.data[DOMAIN][entry.entry_id], key) for key in SWITCHES])


class UtilitySwitch(HeaterEntity, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, key):
        super().__init__(coordinator, key + "_control")
        self.key = key
        self._attr_name, self.on_value = SWITCHES[key]

    @property
    def available(self):
        return super().available and self.key in self.coordinator.data.registers

    @property
    def is_on(self):
        value = self.coordinator.data.registers.get(self.key)
        if value is None:
            return None
        return value & 0xFF == self.on_value if self.key == "advanced_load" else bool(value & 0xFF)

    async def _set(self, value):
        if not self.available:
            raise HomeAssistantError("This heater has not supplied the corresponding utility register")
        await self.coordinator.async_set_value(OPTIONAL_REGISTERS[self.key], value)

    async def async_turn_on(self, **kwargs):
        await self._set(self.on_value)

    async def async_turn_off(self, **kwargs):
        await self._set(0)
