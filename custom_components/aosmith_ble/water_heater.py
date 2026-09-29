"""Water heater entity: measured setpoint and validated mode writes."""

from homeassistant.components.water_heater import WaterHeaterEntity, WaterHeaterEntityFeature
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_MODE_DAYS, DOMAIN, MAX_TEMP_F, MIN_TEMP_F, MODE, MODE_NAMES, MODES, SETPOINT
from .entity import HeaterEntity
from .protocol import encode_temperature, encode_timed_mode


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
        self._attr_supported_features = WaterHeaterEntityFeature.OPERATION_MODE
        self._attr_supported_features |= WaterHeaterEntityFeature.TARGET_TEMPERATURE

    @property
    def target_temperature(self):
        return self.coordinator.data.target_temperature

    @property
    def current_operation(self):
        return MODE_NAMES.get(self.coordinator.data.mode, "Unknown")

    @property
    def supported_features(self):
        features = WaterHeaterEntityFeature.OPERATION_MODE
        if self.coordinator.data.mode != 2:
            features |= WaterHeaterEntityFeature.TARGET_TEMPERATURE
        return features

    async def async_set_operation_mode(self, operation_mode):
        if operation_mode not in MODES:
            raise HomeAssistantError("Unsupported mode")
        # Custom duration is available on the device page and through our action.
        value = {
            "Vacation": encode_timed_mode("Vacation", DEFAULT_MODE_DAYS[2]),
            "Guest": encode_timed_mode("Guest", DEFAULT_MODE_DAYS[3]),
        }.get(operation_mode, MODES[operation_mode])
        await self.coordinator.async_set_value(MODE, value)

    async def async_set_temperature(self, **kwargs):
        if self.coordinator.data.mode == 2:
            raise HomeAssistantError("Leave Vacation mode before changing the temperature")
        try:
            temperature = float(kwargs[ATTR_TEMPERATURE])
        except (KeyError, TypeError, ValueError) as err:
            raise HomeAssistantError("Provide a valid temperature") from err
        if not MIN_TEMP_F <= temperature <= self.max_temp:
            raise HomeAssistantError(f"Choose a temperature from {MIN_TEMP_F} to {self.max_temp} °F.")
        await self.coordinator.async_set_value(SETPOINT, encode_temperature(temperature))

    @property
    def extra_state_attributes(self):
        return {
            "vacation_default_days": DEFAULT_MODE_DAYS[2],
            "guest_default_days": DEFAULT_MODE_DAYS[3],
            "duration_control": "Vacation/Guest mode",
        }
