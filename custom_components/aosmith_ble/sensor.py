"""User-facing readings and optional raw diagnostics."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfEnergy, UnitOfTemperature

from .const import DOMAIN
from .entity import HeaterEntity
from .protocol import decode_availability


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            HeaterSensor(coordinator, "target_temperature"),
            HeaterSensor(coordinator, "availability"),
            HeaterSensor(coordinator, "fault"),
            EnergySensor(coordinator),
            TariffSensor(coordinator, entry),
            *[ExtendedSensor(coordinator, key) for key in EXTENDED_SENSORS],
        ]
    )


class HeaterSensor(HeaterEntity, SensorEntity):
    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        self.key = key
        self._attr_name = {
            "target_temperature": "Temperature setpoint",
            "availability": "Hot water availability",
            "fault": "Fault register",
        }[key]
        if key == "availability":
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_suggested_display_precision = 0
            # No state_class: changing calibration must not combine incompatible statistics.
            self.scale = coordinator.options.get("availability_scale", "unverified")
        self._attr_icon = {
            "target_temperature": "mdi:thermometer",
            "availability": "mdi:water",
            "fault": "mdi:alert-circle-outline",
        }[key]
        if key == "target_temperature":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_entity_registry_enabled_default = False
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
            self._attr_suggested_display_precision = 0
        if key == "fault":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self):
        if self.key == "availability":
            return decode_availability(self.coordinator.data.availability, self.scale)
        return getattr(self.coordinator.data, self.key)

    @property
    def extra_state_attributes(self):
        if self.key == "target_temperature":
            return None
        if self.key == "availability":
            return {
                "raw_value": self.coordinator.data.availability,
                "scale": self.scale,
                "calibration": "Select the scale in Configure after comparing with iCOMM",
                "estimated": self.scale == "five_levels",
            }
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
    _attr_entity_registry_enabled_default = False

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


class EnergySensor(HeaterEntity, SensorEntity):
    _attr_name = "Energy usage"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator):
        super().__init__(coordinator, "energy")

    @property
    def available(self):
        return super().available and "energy_wh" in self.coordinator.data.registers

    @property
    def native_value(self):
        value = self.coordinator.data.registers.get("energy_wh")
        return value / 1000 if value is not None else None


class TariffSensor(HeaterEntity, SensorEntity):
    """Persistent plan preview, not a claim of device programming."""

    _attr_name = "Selected tariff"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, "tariff")
        self.plan = entry.options.get("tariff")

    @property
    def available(self):
        # The cache remains readable when Bluetooth or the internet is unavailable.
        return True

    @property
    def native_value(self):
        return self.plan["tariff_name"][:255] if self.plan else "Not selected"

    @property
    def extra_state_attributes(self):
        if not self.plan:
            return {"heater_programming": "not implemented"}
        return {
            "utility": self.plan["utility_name"],
            "tariff_id": self.plan["tariff_id"],
            "tariff": self.plan["tariff_name"],
            "retrieved_at": self.plan["retrieved_at"],
            "source": self.plan["source"],
            "schedule": self.plan["touEvents"],
            "holidays": self.plan["holidays"],
            "heater_programming": "not implemented; selection is a local preview",
        }
