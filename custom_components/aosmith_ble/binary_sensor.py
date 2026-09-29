"""One problem indicator covering the heater's reported fault conditions."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .entity import HeaterEntity
from .faults import fault_details

FLAGS = {
    "fault_present": "Error status",
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

    @property
    def extra_state_attributes(self):
        # Keep the existing unique ID and automation behavior. A failed poll makes
        # this entity unavailable; stale code 0 must not be displayed as healthy.
        if not self.available:
            return {"description": "Heater status unavailable"}
        return fault_details(self.coordinator.data.fault)
