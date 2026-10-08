"""Hot-water availability and cumulative energy usage."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfEnergy

from .const import DOMAIN
from .entity import HeaterEntity
from .protocol import decode_availability
from .tariff import tariff_label
from .timing import DR_NAMES, decode_dr


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            HeaterSensor(coordinator, "availability"),
            EnergySensor(coordinator),
            TariffSensor(coordinator),
            HotWaterLevel(coordinator),
            ActiveDRLevel(coordinator),
            ClockStatus(coordinator),
        ]
    )


class ClockStatus(HeaterEntity, SensorEntity):
    _attr_name = "Clock synchronization"
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, coordinator):
        super().__init__(coordinator, "clock_synchronization")

    @property
    def available(self):
        return True

    @property
    def native_value(self):
        return self.coordinator.clock_guard.data["status"]

    @property
    def extra_state_attributes(self):
        return dict(self.coordinator.clock_guard.data)


class ActiveDRLevel(HeaterEntity, SensorEntity):
    _attr_name = "Active demand response"
    _attr_icon = "mdi:transmission-tower"

    def __init__(self, coordinator):
        super().__init__(coordinator, "active_dr_level")

    @property
    def available(self):
        return super().available and decode_dr(self.coordinator.data.registers.get("dr_status")) is not None

    @property
    def native_value(self):
        return DR_NAMES.get(decode_dr(self.coordinator.data.registers.get("dr_status")))

    @property
    def extra_state_attributes(self):
        return {"raw_value": self.coordinator.data.registers.get("dr_status")}


class HotWaterLevel(HeaterEntity, SensorEntity):
    _attr_name = "Hot water level"
    _attr_icon = "mdi:water"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["Low", "Medium", "High"]

    def __init__(self, coordinator):
        super().__init__(coordinator, "hot_water_level")

    @property
    def native_value(self):
        return {0: "Low", 5: "Medium", 10: "High"}.get(self.coordinator.data.availability)

    @property
    def extra_state_attributes(self):
        state = self.coordinator.data
        return {
            "raw_value": state.availability,
            "raw_word": state.availability_word,
            "last_read_at": state.availability_read_at,
            "interpretation": "Heater-reported category; not measured remaining tank volume",
        }


class TariffSensor(HeaterEntity, SensorEntity):
    _attr_name = "Electricity tariff"
    _attr_icon = "mdi:transmission-tower"

    def __init__(self, coordinator):
        super().__init__(coordinator, "electricity_rate")

    @property
    def available(self):
        # Configuration remains useful when the heater is temporarily offline.
        return True

    @property
    def native_value(self):
        status = self.coordinator.tariff_status
        if status in ("Updating", "Update incomplete"):
            return status
        return tariff_label(self.coordinator.tariff_plan)

    @property
    def extra_state_attributes(self):
        plan = self.coordinator.tariff_plan or {}
        state = self.coordinator.tariff_state or {}
        return {
            "utility": plan.get("utility_name"),
            "rate_plan": plan.get("tariff_name"),
            "savings_preference": self.coordinator.tariff_preference,
            "status": self.coordinator.tariff_status,
            "last_updated": state.get("applied_at"),
        }


class HeaterSensor(HeaterEntity, SensorEntity):
    _attr_name = "Hot water availability index"
    _attr_entity_registry_enabled_default = False
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:water"
    # No state_class: a calibration change must not mix incompatible statistics.

    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)

    @property
    def native_value(self):
        return decode_availability(self.coordinator.data.availability)

    @property
    def extra_state_attributes(self):
        raw = self.coordinator.data.availability
        return {
            "raw_value": raw,
            "category": {0: "Low", 5: "Medium", 10: "High"}.get(raw, "Unknown"),
            "interpretation": "HPS10 categories, not measured remaining tank volume",
        }


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
