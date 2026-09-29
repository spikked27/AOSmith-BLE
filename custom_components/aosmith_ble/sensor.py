"""Raw availability and fault values without unverified unit conversions."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory, UnitOfTemperature

from .const import DOMAIN
from .entity import HeaterEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            HeaterSensor(coordinator, "target_temperature"),
            HeaterSensor(coordinator, "availability"),
            HeaterSensor(coordinator, "fault"),
            *[ExtendedSensor(coordinator, key) for key in EXTENDED_SENSORS],
        ]
    )


class HeaterSensor(HeaterEntity, SensorEntity):
    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        self.key = key
        self._attr_name = {
            "target_temperature": "Temperature setpoint",
            "availability": "Hot water availability level",
            "fault": "Fault register",
        }[key]
        self._attr_icon = {
            "target_temperature": "mdi:thermometer",
            "availability": "mdi:water",
            "fault": "mdi:alert-circle-outline",
        }[key]
        if key == "target_temperature":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
            self._attr_suggested_display_precision = 0
        if key == "fault":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        return getattr(self.coordinator.data, self.key)

    @property
    def extra_state_attributes(self):
        if self.key == "target_temperature":
            return None
        if self.key == "availability":
            return {"scale": "raw device level; percentage mapping unverified"}
        return {"raw_hex": f"{self.coordinator.data.fault:04X}"}


EXTENDED_SENSORS = {
    "maximum_setpoint": "Device maximum setpoint",
    "remote_setpoint": "Remote setpoint register",
    "vacation_days": "Vacation remaining days",
    "guest_days": "Guest remaining days",
    "electric_days": "Electric remaining days",
}


class ExtendedSensor(HeaterEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        self.key = key
        self._attr_name = EXTENDED_SENSORS[key]
        if "setpoint" in key:
            self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_suggested_display_precision = 0
        else:
            self._attr_icon = "mdi:calendar-clock"
            # Raw 100 can represent the app's "On" sentinel; no duration unit assigned.

    @property
    def available(self):
        return super().available and self.key in self.coordinator.data.registers

    @property
    def native_value(self):
        from .protocol import decode_temperature

        raw = self.coordinator.data.registers.get(self.key)
        if raw is None:
            return None
        return decode_temperature(raw) if "setpoint" in self.key else raw & 0xFF

    @property
    def extra_state_attributes(self):
        return (
            {"interpretation": "APK-derived; duration 100 may mean continuously on"}
            if "days" in self.key
            else None
        )
