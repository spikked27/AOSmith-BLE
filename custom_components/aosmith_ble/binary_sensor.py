"""Read-only utility status and fault presence."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .entity import HeaterEntity

FLAGS = {
    "fault_present": "Fault present",
    "cta_present": "CTA utility module present",
    "utility_enrollment": "Utility enrollment device flag",
    "utility_override": "Utility demand response paused",
    "advanced_load": "Advanced load-up enabled",
}


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([StatusSensor(hass.data[DOMAIN][entry.entry_id], key) for key in FLAGS])


class StatusSensor(HeaterEntity, BinarySensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        self.key = key
        self._attr_name = FLAGS[key]
        if key == "fault_present":
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def available(self):
        return super().available and (
            self.key == "fault_present" or self.key in self.coordinator.data.registers
        )

    @property
    def is_on(self):
        if self.key == "fault_present":
            return bool(self.coordinator.data.fault & 0xFF)
        value = self.coordinator.data.registers.get(self.key)
        if value is None:
            return None
        return (value & 0xFF) == 0xA5 if self.key == "advanced_load" else bool(value & 0xFF)
