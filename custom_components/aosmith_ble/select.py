"""One-step Vacation control and optional Hot Water Plus."""

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, HOT_WATER_PLUS, MODE, MODE_NAMES
from .entity import HeaterEntity
from .protocol import encode_timed_mode


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [Vacation(coordinator)]
    if entry.options.get("enable_hot_water_plus", False):
        entities.append(HotWaterPlus(coordinator))
    async_add_entities(entities)


class Vacation(HeaterEntity, SelectEntity):
    """Start Vacation and its duration in one command."""

    _attr_name = "Vacation"
    _attr_icon = "mdi:bag-suitcase"
    _attr_options = ["Off", "Until changed"] + [
        "1 day" if days == 1 else f"{days} days" for days in range(1, 100)
    ]

    def __init__(self, coordinator):
        super().__init__(coordinator, "vacation_duration")

    @property
    def current_option(self):
        state = self.coordinator.data
        if state.mode != 2:
            return "Off"
        raw = state.registers.get("vacation_days")
        if raw is None:
            return None
        days = raw & 0xFF
        if days == 100:
            return "Until changed"
        option = "1 day" if days == 1 else f"{days} days"
        return option if option in self.options else None

    @property
    def extra_state_attributes(self):
        return {
            "active_mode": MODE_NAMES.get(self.coordinator.data.mode),
            "behavior": "Selecting days enters Vacation and starts the countdown from now",
            "exit_mode": "Hybrid",
        }

    async def async_select_option(self, option):
        if not self.available or option not in self.options:
            raise HomeAssistantError("Choose a valid Vacation duration on a connected heater")
        mode = self.coordinator.data.mode
        if option == "Off":
            if mode != 2:
                return
            value = 4  # Explicitly return to Hybrid, never guess a previous mode.
        else:
            days = 100 if option == "Until changed" else int(option.split()[0])
            value = encode_timed_mode("Vacation", days)
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
