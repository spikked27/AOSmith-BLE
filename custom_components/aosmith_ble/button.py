"""Clock synchronization and opt-in diagnostic tools."""

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .entity import HeaterEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            DebugButton(coordinator, "refresh"),
            DebugButton(coordinator, "reconnect"),
            DebugButton(coordinator, "inspect"),
            DebugButton(coordinator, "inspect_schedule"),
            DebugButton(coordinator, "inspect_dr"),
            DebugButton(coordinator, "start_dr_monitor"),
            DebugButton(coordinator, "stop_dr_monitor"),
            ClockButton(coordinator),
        ]
    )


class ClockButton(HeaterEntity, ButtonEntity):
    _attr_name = "Synchronize clock"
    _attr_icon = "mdi:clock-check-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator):
        super().__init__(coordinator, "set_clock")

    async def async_press(self):
        await self.coordinator.async_set_clock()


class DebugButton(HeaterEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, action):
        super().__init__(coordinator, action)
        self.action = action
        self._attr_name = {
            "refresh": "Refresh readings",
            "reconnect": "Reconnect Bluetooth",
            "inspect": "Inspect extended registers",
            "inspect_schedule": "Read stored tariff schedule",
            "inspect_dr": "Capture DR status",
            "start_dr_monitor": "Monitor DR for 3 hours",
            "stop_dr_monitor": "Stop DR monitoring",
        }[action]
        self._attr_icon = "mdi:refresh" if action == "refresh" else "mdi:bluetooth-connect"

    @property
    def available(self):
        # Recovery actions must remain usable after a failed poll/disconnect.
        return True

    async def async_press(self):
        if self.action == "inspect_dr":
            await self.coordinator.async_capture_dr_status()
            return
        if self.action == "start_dr_monitor":
            await self.coordinator.dr.async_start()
            return
        if self.action == "stop_dr_monitor":
            await self.coordinator.dr.async_stop()
            return
        if self.action == "inspect":
            await self.coordinator.async_inspect_registers()
            return
        if self.action == "inspect_schedule":
            await self.coordinator.async_inspect_schedule()
            return
        if self.action == "reconnect":
            async with self.coordinator.command_lock:
                await self.coordinator.client.disconnect()
        await self.coordinator.async_request_refresh()
