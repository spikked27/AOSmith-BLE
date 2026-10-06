"""Hot-water availability and cumulative energy usage."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfEnergy

from .const import DOMAIN, VERSION
from .entity import HeaterEntity
from .protocol import decode_availability
from .tariff import tariff_label


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            HeaterSensor(coordinator, "availability"),
            EnergySensor(coordinator),
            TariffSensor(coordinator),
            DiagnosticReadStatus(coordinator),
            IntegrationVersion(coordinator),
        ]
    )


class DiagnosticReadStatus(HeaterEntity, SensorEntity):
    _attr_name = "Diagnostic read status"
    _attr_icon = "mdi:clipboard-check-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator):
        super().__init__(coordinator, "diagnostic_read_status")

    @property
    def available(self):
        return True

    @property
    def native_value(self):
        return self.coordinator.diagnostic_status["status"]

    @property
    def extra_state_attributes(self):
        return dict(self.coordinator.diagnostic_status)


class IntegrationVersion(HeaterEntity, SensorEntity):
    _attr_name = "Integration version"
    _attr_icon = "mdi:information-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator):
        super().__init__(coordinator, "integration_version")

    @property
    def available(self):
        return True

    @property
    def native_value(self):
        return VERSION

    @property
    def extra_state_attributes(self):
        installed = self.coordinator.installed_version
        return {
            "running_version": VERSION,
            "downloaded_version": installed,
            "restart_required": installed is not None and installed != VERSION,
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
    _attr_name = "Hot water availability"
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
