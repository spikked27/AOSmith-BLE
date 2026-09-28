"""Raw availability and fault values without unverified unit conversions."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .entity import HeaterEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HeaterSensor(coordinator, "availability"), HeaterSensor(coordinator, "fault")])


class HeaterSensor(HeaterEntity, SensorEntity):
    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        self.key = key
        self._attr_name = "Hot water availability level" if key == "availability" else "Fault register"
        self._attr_icon = "mdi:water" if key == "availability" else "mdi:alert-circle-outline"
        if key == "fault":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        return getattr(self.coordinator.data, self.key)

    @property
    def extra_state_attributes(self):
        if self.key == "availability":
            return {"scale": "raw device level; percentage mapping unverified"}
        return {"raw_hex": f"{self.coordinator.data.fault:04X}"}
