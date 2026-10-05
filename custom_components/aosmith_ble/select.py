"""Vacation/Guest duration control and optional Hot Water Plus."""

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_ENERGY_PREFERENCE, DOMAIN, ENERGY_PREFERENCES, HOT_WATER_PLUS, MODE, MODE_NAMES
from .entity import HeaterEntity
from .protocol import encode_timed_mode


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [VacationGuestDuration(coordinator)]
    if entry.options.get("enable_hot_water_plus", False):
        entities.append(HotWaterPlus(coordinator))
    if entry.options.get(CONF_ENERGY_PREFERENCE, False):
        entities.append(ExperimentalEnergyPreference(coordinator))
    async_add_entities(entities)


class ExperimentalEnergyPreference(HeaterEntity, SelectEntity):
    """App-derived candidate, explicitly not a verified behavioral control."""

    _attr_name = "Energy preference (experimental)"
    _attr_icon = "mdi:water-boiler"
    _attr_options = list(ENERGY_PREFERENCES)

    def __init__(self, coordinator):
        super().__init__(coordinator, "energy_preference_experimental")

    @property
    def current_option(self):
        raw = self.coordinator.data.registers.get("energy_preference_experimental")
        return next((name for name, value in ENERGY_PREFERENCES.items() if value == raw), None)

    @property
    def extra_state_attributes(self):
        return {
            "behavior_verified": False,
            "schedule_rebuilt": False,
            "original_value": (self.coordinator.preference_backup or {}).get("value"),
        }

    async def async_select_option(self, option):
        await self.coordinator.async_test_energy_preference(option)


class VacationGuestDuration(HeaterEntity, SelectEntity):
    """Adjust the active Vacation/Guest countdown; other modes display Off."""

    _attr_name = "Vacation/Guest mode"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator):
        # Preserve the released control's entity identity and user customizations.
        super().__init__(coordinator, "vacation_duration")

    @property
    def options(self):
        mode = self.coordinator.data.mode
        if mode not in (2, 3):
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
        if state.mode not in (2, 3):
            return "Off"
        key = "vacation_days" if state.mode == 2 else "guest_days"
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
            "behavior": "Select Vacation or Guest on the water heater, then adjust its days here",
            "exit_mode": "Hybrid",
        }

    async def async_select_option(self, option):
        if not self.available or option not in self.options:
            raise HomeAssistantError("Select Vacation or Guest on the water heater before adjusting its days")
        mode = self.coordinator.data.mode
        if option == "Off":
            if mode not in (2, 3):
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
