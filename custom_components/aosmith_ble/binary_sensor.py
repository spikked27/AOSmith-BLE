"""Fault presence; utility flags remain in read-only research diagnostics."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .entity import HeaterEntity

FLAGS = {
    "fault_present": "Fault present",
}


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([StatusSensor(hass.data[DOMAIN][entry.entry_id], key) for key in FLAGS])


class StatusSensor(HeaterEntity, BinarySensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        self.key = key
        self._attr_name = FLAGS[key]
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self):
        return bool(self.coordinator.data.fault & 0xFF)
