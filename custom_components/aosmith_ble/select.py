"""Device-page duration control and optional Hot Water Plus."""

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, HOT_WATER_PLUS, MODE, MODE_NAMES, TIMED_MODE_REGISTERS
from .entity import HeaterEntity
from .protocol import encode_timed_mode


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [ModeDuration(coordinator)]
    if entry.options.get("enable_hot_water_plus", False):
        entities.append(HotWaterPlus(coordinator))
    async_add_entities(entities)


class ModeDuration(HeaterEntity, SelectEntity):
    """Show the active mode's countdown; selecting a value restarts that timer."""

    _attr_name = "Mode duration"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator):
        super().__init__(coordinator, "mode_duration")

    @property
    def available(self):
        return super().available and self.coordinator.data.mode in TIMED_MODE_REGISTERS

    @property
    def options(self):
        mode = self.coordinator.data.mode
        if mode not in TIMED_MODE_REGISTERS:
            return []
        maximum = 7 if mode == 3 else 99
        return (["Until changed"] if mode in (1, 2) else []) + [
            "1 day" if days == 1 else f"{days} days" for days in range(1, maximum + 1)
        ]

    @property
    def current_option(self):
        state = self.coordinator.data
        if state.mode not in TIMED_MODE_REGISTERS:
            return None
        key, _ = TIMED_MODE_REGISTERS[state.mode]
        # These are the same remaining-days registers used by iCOMM. Do not
        # substitute a stale command or a different mode's retained countdown.
        raw = state.registers.get(key)
        if raw is None:
            return None
        days = raw & 0xFF
        if (state.mode == 2 and days == 100) or (state.mode == 1 and days == 0):
            return "Until changed"
        option = "1 day" if days == 1 else f"{days} days"
        return option if option in self.options else None

    @property
    def extra_state_attributes(self):
        return {
            "active_mode": MODE_NAMES.get(self.coordinator.data.mode),
            "behavior": "Selecting a duration starts that countdown from now",
        }

    async def async_select_option(self, option):
        mode = self.coordinator.data.mode
        if not self.available or option not in self.options:
            raise HomeAssistantError("Select Vacation, Guest or Electric first, then choose a duration")
        if option == "Until changed":
            value = 0x6402 if mode == 2 else 1
        else:
            value = encode_timed_mode(MODE_NAMES[mode], int(option.split()[0]))
        # Check the live mode inside the transport lock, not just this UI snapshot.
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
