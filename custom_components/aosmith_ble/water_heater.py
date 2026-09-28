"""Water heater entity: measured setpoint and validated mode writes."""

from homeassistant.components.water_heater import WaterHeaterEntity, WaterHeaterEntityFeature
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, MAX_TEMP_F, MIN_TEMP_F, MODE, MODE_NAMES, MODES, SETPOINT
from .entity import HeaterEntity
from .protocol import encode_temperature


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([Heater(hass.data[DOMAIN][entry.entry_id], entry)])


class Heater(HeaterEntity, WaterHeaterEntity):
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_min_temp = MIN_TEMP_F
    _attr_max_temp = MAX_TEMP_F
    _attr_target_temperature_step = 1
    _attr_operation_list = list(MODES)

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, "water_heater")
        self._setpoint_enabled = entry.options.get("enable_setpoint_writes", False)
        self._attr_supported_features = WaterHeaterEntityFeature.OPERATION_MODE
        if self._setpoint_enabled:
            self._attr_supported_features |= WaterHeaterEntityFeature.TARGET_TEMPERATURE

    @property
    def target_temperature(self):
        return self.coordinator.data.target_temperature

    @property
    def current_operation(self):
        return MODE_NAMES.get(self.coordinator.data.mode, "Unknown")

    async def async_set_operation_mode(self, operation_mode):
        if operation_mode not in MODES:
            raise HomeAssistantError("Unsupported mode")
        await self.coordinator.async_set_value(MODE, MODES[operation_mode])

    async def async_set_temperature(self, **kwargs):
        if not self._setpoint_enabled:
            raise HomeAssistantError("Enable experimental setpoint writes in integration options first")
        temperature = float(kwargs[ATTR_TEMPERATURE])
        if not MIN_TEMP_F <= temperature <= MAX_TEMP_F:
            raise HomeAssistantError(f"Choose a temperature from {MIN_TEMP_F} to {MAX_TEMP_F} °F")
        await self.coordinator.async_set_value(SETPOINT, encode_temperature(temperature))
