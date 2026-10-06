"""Savings, timed modes and supported Hot Water Plus controls."""

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    ENERGY_PREFERENCES,
    HOT_WATER_PLUS,
    MODE,
    MODE_NAMES,
    TIMED_MODE_REGISTERS,
)
from .entity import HeaterEntity
from .protocol import encode_timed_mode


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [VacationGuestDuration(coordinator), SavingsPreference(coordinator)]
    if coordinator.data.registers.get("hot_water_plus") in range(4):
        entities.append(HotWaterPlus(coordinator))
    async_add_entities(entities)


class SavingsPreference(HeaterEntity, SelectEntity):
    """Apply the selected preference to the entire configured tariff schedule."""

    _attr_name = "Savings preference"
    _attr_icon = "mdi:piggy-bank-outline"
    _attr_options = list(ENERGY_PREFERENCES)

    def __init__(self, coordinator):
        super().__init__(coordinator, "energy_preference_experimental")

    @property
    def current_option(self):
        return self.coordinator.tariff_preference

    @property
    def available(self):
        return super().available and bool(self.coordinator.tariff_plan) and not self.coordinator.tariff_busy

    async def async_select_option(self, option):
        await self.coordinator.async_set_energy_preference(option)


class VacationGuestDuration(HeaterEntity, SelectEntity):
    """Adjust the active Electric, Vacation or Guest countdown."""

    _attr_name = "Mode duration"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator):
        # Preserve the released control's entity identity and user customizations.
        super().__init__(coordinator, "vacation_duration")

    @property
    def options(self):
        mode = self.coordinator.data.mode
        if mode not in TIMED_MODE_REGISTERS:
            return ["Off"]
        maximum = 99 if mode == 2 else 7
        return (
            ["Off"]
            + (["Until changed"] if mode == 2 else [])
            + ["1 day" if days == 1 else f"{days} days" for days in range(1, maximum + 1)]
        )

    @property
    def current_option(self):
        state = self.coordinator.data
        if state.mode not in TIMED_MODE_REGISTERS:
            return "Off"
        key, _register = TIMED_MODE_REGISTERS[state.mode]
        raw = state.registers.get(key)
        days = (raw & 0xFF) if raw is not None else state.mode_days
        if state.mode == 2 and days == 100:
            return "Until changed"
        option = "1 day" if days == 1 else f"{days} days"
        return option if option in self.options else None

    @property
    def extra_state_attributes(self):
        return {
            "active_mode": MODE_NAMES.get(self.coordinator.data.mode),
        }

    async def async_select_option(self, option):
        if not self.available or option not in self.options:
            raise HomeAssistantError("Select Electric, Vacation or Guest before adjusting its duration")
        mode = self.coordinator.data.mode
        if option == "Off":
            if mode not in TIMED_MODE_REGISTERS:
                return
            value = 4
        else:
            days = 100 if option == "Until changed" else int(option.split()[0])
            value = encode_timed_mode(MODE_NAMES[mode], days)
        await self.coordinator.async_set_value(MODE, value, expected_mode=mode)


class HotWaterPlus(HeaterEntity, SelectEntity):
    _attr_name = "Hot Water Plus"
    _attr_options = ["Off", "Level 1", "Level 2", "Level 3"]
    _attr_icon = "mdi:water-plus"

    def __init__(self, coordinator):
        super().__init__(coordinator, "hot_water_plus")

    @property
    def available(self):
        return super().available and self.coordinator.data.registers.get("hot_water_plus") in range(4)

    @property
    def current_option(self):
        value = self.coordinator.data.registers.get("hot_water_plus")
        return self.options[value] if value in range(4) else None

    async def async_select_option(self, option):
        if option not in self.options or not self.available:
            raise HomeAssistantError("Hot Water Plus is not available on this heater")
        if self.coordinator.data.mode not in (1, 4, 5):
            raise HomeAssistantError("Hot Water Plus requires Electric, Hybrid or Heat pump mode")
        await self.coordinator.async_set_value(HOT_WATER_PLUS, self.options.index(option))
