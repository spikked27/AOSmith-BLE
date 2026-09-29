"""Hot-water availability and cumulative energy usage."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfEnergy

from .const import DOMAIN
from .entity import HeaterEntity
from .protocol import decode_availability


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HeaterSensor(coordinator, "availability"), EnergySensor(coordinator)])


class HeaterSensor(HeaterEntity, SensorEntity):
    _attr_name = "Hot water availability"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:water"
    # No state_class: a calibration change must not mix incompatible statistics.

    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        self.scale = coordinator.options.get("availability_scale", "unverified")

    @property
    def native_value(self):
        return decode_availability(self.coordinator.data.availability, self.scale)

    @property
    def extra_state_attributes(self):
        attributes = {
            "raw_value": self.coordinator.data.availability,
            "scale": self.scale,
            "calibration": "Choose HPS10 observed categories in Configure for the tested model",
        }
        if self.scale == "hps10_observed":
            attributes.update(
                category={0: "Medium", 5: "High"}.get(self.coordinator.data.availability, "Unknown"),
                interpretation="Observed HPS10 categories; percentage is not measured tank volume",
                calibration="HPS10-80H45DV firmware 6.4; Low code not yet identified",
            )
        return attributes


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
