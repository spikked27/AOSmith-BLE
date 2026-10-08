"""Home Assistant Bluetooth adapter and polling coordinator."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth, persistent_notification
from homeassistant.const import CONF_ADDRESS
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import HeaterClient
from .clock import ClockHistory
from .clock_guard import ClockGuard
from .const import (
    CLOCK_STATUS_REGISTERS,
    CONF_AUTO_CLOCK,
    CONF_ENERGY_PREFERENCE,
    CONF_IDENTIFIER,
    CONF_INTERVAL,
    CONF_PIN,
    DEFAULT_INTERVAL,
    DOMAIN,
    ENERGY,
    ENERGY_PREFERENCE,
    ENERGY_PREFERENCES,
    HOT_WATER_PLUS,
    INSPECT_REGISTERS,
    NAME,
    VERSION,
)
from .dr import DRMonitor
from .protocol import ProtocolError
from .schedule import build_schedule, validate_payloads
from .tariff import TariffError

LOGGER = logging.getLogger(__name__)


def _read_saved_preference(path):
    """Verify the durable copy; HA Store logs some write errors without raising."""
    return json.loads(Path(path).read_text())["data"]


def _installed_version():
    return json.loads(Path(__file__).with_name("manifest.json").read_text())["version"]


def make_client(hass, data):
    """Use HA's shared Bluetooth infrastructure, including active proxies."""
    address = data[CONF_ADDRESS]

    def get_device():
        return bluetooth.async_ble_device_from_address(hass, address, connectable=True)

    async def connect(disconnected_callback):
        device = get_device()
        if device is None:
            raise BleakError(
                "Heater is not visible to a connectable Bluetooth adapter; enable heater Bluetooth"
            )
        return await establish_connection(
            BleakClientWithServiceCache,
            device,
            NAME,
            disconnected_callback=disconnected_callback,
            ble_device_callback=get_device,
            max_attempts=2,
        )

    return HeaterClient(connect, data[CONF_PIN], data[CONF_IDENTIFIER])


class HeaterCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        self.client = make_client(hass, entry.data)
        self.options = dict(entry.options)
        self.entry = entry
        self.preference_backup = None
        # Keep the old 28:113 backup intact; never restore it into a different register.
        self.preference_store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.energy_preference_28_75")
        self.preference_backup_loaded = False
        self.tariff_store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.tariff")
        self.tariff_state = None
        self.tariff_busy = False
        self._preference_task = None
        self.diagnostic_status = {"status": "Idle"}
        self.installed_version = VERSION
        # Core controls and readings always request their supporting registers.
        self.client.optional_registers["energy_wh"] = ENERGY
        self.client.optional_registers["hot_water_plus"] = HOT_WATER_PLUS
        self.client.optional_registers["energy_preference_experimental"] = ENERGY_PREFERENCE
        self.client.optional_registers.update(CLOCK_STATUS_REGISTERS)
        self.address = entry.data[CONF_ADDRESS]
        self.command_lock = asyncio.Lock()
        self.clock = ClockHistory(hass, entry, self.client, self.local_now)
        self.clock_guard = ClockGuard(hass, self)
        self.dr = DRMonitor(hass, self)
        super().__init__(
            hass,
            LOGGER,
            name=NAME,
            config_entry=entry,
            update_interval=timedelta(seconds=entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL)),
            always_update=False,
        )

    async def _async_update_data(self):
        async with self.command_lock:
            previous_version = self.installed_version
            try:
                self.installed_version = await self.hass.async_add_executor_job(_installed_version)
            except (OSError, ValueError, KeyError):
                self.installed_version = None
            if previous_version != self.installed_version:
                # A code download must update the version entity even if heater data is unchanged.
                self.async_update_listeners()
            if not self.preference_backup_loaded:
                self.preference_backup = await self.preference_store.async_load()
                self.preference_backup_loaded = True
            if self.tariff_state is None:
                self.tariff_state = await self.tariff_store.async_load() or {}
            try:
                state = await self.client.read_state()
            except (BleakError, TimeoutError, ProtocolError) as err:
                self.clock_guard.unavailable()
                raise UpdateFailed(str(err)) from err
            try:
                await self.dr.async_load()
                await self.clock.async_load()
            except (OSError, ValueError) as err:
                LOGGER.warning("Could not load diagnostic history: %s", type(err).__name__)
            try:
                if self.tariff_busy:
                    self.clock_guard.reset_observations("Tariff update in progress")
                else:
                    await self.clock_guard.async_observe(state)
            except (OSError, ValueError, KeyError, TypeError) as err:
                # A malformed/unavailable tariff must not hide the heater's core readings.
                self.clock_guard.unavailable("Clock verification data unavailable")
                LOGGER.warning("Clock verification unavailable: %s", type(err).__name__)
            return state

    async def async_set_automatic_clock(self, enabled):
        async with self.command_lock:
            self.options[CONF_AUTO_CLOCK] = enabled
            self.clock_guard.reset_observations()
            self.hass.config_entries.async_update_entry(
                self.entry, options={**self.entry.options, CONF_AUTO_CLOCK: enabled}
            )
            self.async_update_listeners()

    @property
    def tariff_plan(self):
        state = self.tariff_state or {}
        return state.get("applied_plan") or self.options.get("tariff")

    @property
    def tariff_preference(self):
        if not self.tariff_plan:
            return None
        state = self.tariff_state or {}
        return state.get("applied_preference", self.options.get("tariff_preference"))

    @property
    def tariff_status(self):
        if self.tariff_busy:
            return "Updating"
        state = self.tariff_state or {}
        operation = state.get("last_operation", {})
        if state.get("schedule_incomplete") or operation.get("outcome") == "partial_or_unconfirmed":
            return "Update incomplete"
        return "Configured" if self.tariff_plan else "Not configured"

    async def async_set_energy_preference(self, option):
        if option not in ENERGY_PREFERENCES:
            raise HomeAssistantError("Invalid savings preference")
        if not self.tariff_plan:
            raise HomeAssistantError("Configure an electricity tariff using the integration settings first")
        if self.tariff_busy or (self._preference_task and not self._preference_task.done()):
            raise HomeAssistantError("A tariff update is already running")
        notification_id = f"{DOMAIN}_{self.entry.entry_id}_tariff"

        async def apply():
            persistent_notification.async_create(
                self.hass,
                f"Applying {option}. This can take several minutes. Keep the heater connected.",
                title="Updating AO Smith savings preference",
                notification_id=notification_id,
            )
            try:
                result = await self.async_apply_tariff(self.tariff_plan, option)
            except (HomeAssistantError, asyncio.CancelledError):
                persistent_notification.async_create(
                    self.hass,
                    "The savings preference update did not finish. Check the heater connection and retry.",
                    title="AO Smith tariff update incomplete",
                    notification_id=notification_id,
                )
                raise
            persistent_notification.async_create(
                self.hass,
                f"{option} is now applied. The complete tariff schedule was read back successfully.",
                title="AO Smith savings preference updated",
                notification_id=notification_id,
            )
            return result

        self._preference_task = self.entry.async_create_background_task(
            self.hass, apply(), "aosmith_savings_preference", eager_start=False
        )
        # A websocket disconnect must not cancel an in-progress device upload.
        return await asyncio.shield(self._preference_task)

    async def async_test_energy_preference(self, option=None, *, restore=False):
        if not self.options.get(CONF_ENERGY_PREFERENCE, False):
            raise HomeAssistantError("Enable the experimental energy preference in integration options")
        if not restore and option not in ENERGY_PREFERENCES:
            raise HomeAssistantError("Invalid energy preference")
        if not restore and self.options.get("tariff"):
            return await self.async_apply_tariff(self.options["tariff"], option)
        async with self.command_lock:
            if not self.preference_backup_loaded:
                self.preference_backup = await self.preference_store.async_load()
                self.preference_backup_loaded = True
            if restore:
                backup = self.preference_backup
                if (
                    not isinstance(backup, dict)
                    or backup.get("register") != list(ENERGY_PREFERENCE)
                    or type(backup.get("value")) is not int
                    or backup["value"] not in ENERGY_PREFERENCES.values()
                ):
                    raise HomeAssistantError("No valid saved energy preference is available")
                value = backup["value"]
            else:
                value = ENERGY_PREFERENCES[option]

            async def save_original(before):
                if self.preference_backup is None:
                    backup = {"register": list(ENERGY_PREFERENCE), "value": before}
                    await self.preference_store.async_save(backup)
                    saved = await self.hass.async_add_executor_job(
                        _read_saved_preference, self.preference_store.path
                    )
                    if saved != backup:
                        raise HomeAssistantError(
                            "Could not verify the saved original preference; no write sent"
                        )
                    self.preference_backup = backup

            try:
                result = await self.client.test_energy_preference(value, save_original, restoring=restore)
            except (BleakError, TimeoutError, ProtocolError, OSError, ValueError, KeyError) as err:
                raise HomeAssistantError(str(err)) from err
            finally:
                self.async_update_listeners()
        await self.async_request_refresh()
        return result

    async def async_set_value(self, register, value, *, expected_mode=None):
        async with self.command_lock:
            self.clock_guard.reset_observations()
            try:
                state = await self.client.set_value(register, value, expected_mode=expected_mode)
            except (BleakError, TimeoutError, ProtocolError) as err:
                self.async_set_update_error(UpdateFailed(str(err)))
                raise HomeAssistantError(str(err)) from err
            self.async_set_updated_data(state)

    async def async_inspect_registers(self):
        async with self.command_lock:
            self._start_diagnostic("Extended registers")
            try:
                result = await self.client.inspect_registers(INSPECT_REGISTERS)
            except (BleakError, TimeoutError, ProtocolError) as err:
                self._finish_diagnostic("Failed", detail=type(err).__name__)
                raise HomeAssistantError(str(err)) from err
            rows = list(result["registers"].values())
            succeeded = sum(row["raw"] is not None for row in rows)
            unread = sum(row["error"] == "Not read" for row in rows)
            failed = len(rows) - succeeded - unread
            status = "Incomplete" if unread else "Complete with errors" if failed else "Complete"
            self._finish_diagnostic(status, successful=succeeded, errors=failed, unread=unread)
        await self.async_request_refresh()
        return result

    def _start_diagnostic(self, operation):
        self.diagnostic_status = {
            "status": "Reading",
            "operation": operation,
            "started_at": self.local_now().isoformat(),
            "completed_at": None,
        }
        persistent_notification.async_dismiss(self.hass, f"{DOMAIN}_{self.entry.entry_id}_read")
        self.async_update_listeners()

    def _finish_diagnostic(self, status, **details):
        self.diagnostic_status.update(
            {"status": status, "completed_at": self.local_now().isoformat(), **details}
        )
        self.async_update_listeners()
        summary = ", ".join(f"{key}: {value}" for key, value in details.items())
        persistent_notification.async_create(
            self.hass,
            f"{self.diagnostic_status['operation']}: {status}. {summary}. "
            "The read has stopped; you can download diagnostics now.",
            title="AO Smith diagnostic read finished",
            notification_id=f"{DOMAIN}_{self.entry.entry_id}_read",
        )

    def local_now(self):
        return datetime.now(ZoneInfo(self.hass.config.time_zone))

    async def async_capture_dr_status(self):
        self._start_diagnostic("DR status")
        try:
            result = await self.dr.async_capture()
        except (BleakError, TimeoutError, ProtocolError, OSError, ValueError) as err:
            self._finish_diagnostic("Failed", detail=type(err).__name__)
            raise HomeAssistantError("DR capture failed; check diagnostic read status") from err
        succeeded = sum(row["raw"] is not None for row in result["registers"].values())
        self._finish_diagnostic(
            "Complete" if result["complete"] else "Complete with errors",
            successful=succeeded,
            errors=len(result["registers"]) - succeeded,
        )
        return result

    async def async_set_clock(self):
        async with self.command_lock:
            self.clock_guard.reset_observations("Manual clock setting; awaiting verification")
            previous = self.client.clock_operation
            try:
                result = await self.client.set_clock(self.local_now)
            except (BleakError, TimeoutError, ProtocolError, ValueError) as err:
                raise HomeAssistantError(str(err)) from err
            finally:
                if self.client.clock_operation is not previous:
                    await self.clock.async_record_operation(self.client.clock_operation, reason="manual")
        await self.async_request_refresh()
        return result

    async def async_inspect_schedule(self):
        async with self.command_lock:
            self._start_diagnostic("Stored tariff schedule")
            try:
                result = await self.client.inspect_schedule()
            except (BleakError, TimeoutError, ProtocolError) as err:
                self._finish_diagnostic("Failed", detail=type(err).__name__)
                raise HomeAssistantError(str(err)) from err
            self._finish_diagnostic(
                "Complete" if result["complete"] else "Complete with errors",
                seasons=len(result["seasons"]),
                errors=len(result["errors"]),
            )
        await self.async_request_refresh()
        return result

    async def async_apply_tariff(self, plan=None, preference=None, *, restore=False):
        if self.tariff_busy:
            raise HomeAssistantError("A tariff update is already running")
        self.tariff_busy = True
        self.async_update_listeners()
        try:
            return await self._async_apply_tariff(plan, preference, restore=restore)
        finally:
            self.tariff_busy = False
            self.async_update_listeners()

    async def _async_apply_tariff(self, plan, preference, *, restore):
        async with self.command_lock:
            self.clock_guard.reset_observations()
            if self.tariff_state is None:
                self.tariff_state = await self.tariff_store.async_load() or {}
            if self.tariff_state.get("last_operation", {}).get("outcome") == "partial_or_unconfirmed":
                self.tariff_state["schedule_incomplete"] = True
            try:
                self.client.schedule_operation = {
                    "time": self.local_now().isoformat(),
                    "outcome": "not_sent",
                    "phase": "preparing",
                }
                if restore:
                    schedule = self.tariff_state.get("original")
                    if not isinstance(schedule, dict):
                        raise HomeAssistantError("No original schedule has been saved")
                    validate_payloads(schedule)
                else:
                    self.tariff_state["candidate_plan"] = plan
                    self.tariff_state["requested_preference"] = preference
                    self.tariff_state["last_operation"] = self.client.schedule_operation
                    # Preserve the real API input even if generation fails or HA is interrupted.
                    await self.tariff_store.async_save(self.tariff_state)
                    LOGGER.info("Preparing tariff schedule: %s", preference)
                    schedule = await self.hass.async_add_executor_job(build_schedule, plan, preference)
                    self.tariff_state["generated_schedule"] = schedule

                async def save_original(original):
                    if "original" not in self.tariff_state:
                        state = {
                            **self.tariff_state,
                            "original": original,
                            "last_operation": self.client.schedule_operation,
                        }
                        await self.tariff_store.async_save(state)
                        saved = await self.hass.async_add_executor_job(
                            _read_saved_preference, self.tariff_store.path
                        )
                        if saved != state:
                            raise HomeAssistantError(
                                "Could not save the original schedule; no tariff writes sent"
                            )
                        self.tariff_state = state
                        self.async_update_listeners()

                result = await self.client.apply_schedule(
                    schedule,
                    save_original,
                    restoring=restore,
                )
                if not restore:
                    if result.get("outcome") != "readback_confirmed":
                        raise HomeAssistantError("The heater has not confirmed the tariff upload")
                    self.tariff_state.update(
                        {
                            "applied_plan": plan,
                            "applied_preference": preference,
                            "applied_schedule": schedule,
                            "applied_at": self.local_now().isoformat(),
                        }
                    )
                    self.options.update({"tariff": plan, "tariff_preference": preference})
            except asyncio.CancelledError:
                self.client.schedule_operation["interrupted"] = True
                self.client.schedule_operation["error"] = "Operation cancelled; no automatic write replay"
                LOGGER.warning("Tariff operation interrupted; inspect diagnostics before retrying")
                raise
            except (
                BleakError,
                TimeoutError,
                ProtocolError,
                TariffError,
                ValueError,
                OSError,
                KeyError,
                HomeAssistantError,
            ) as err:
                self.client.schedule_operation["error"] = (
                    str(err)
                    if isinstance(err, (ProtocolError, TariffError, ValueError))
                    else type(err).__name__
                )
                raise HomeAssistantError(str(err)) from err
            finally:
                outcome = self.client.schedule_operation.get("outcome")
                if outcome in ("partial_or_unconfirmed", "readback_confirmed"):
                    self.tariff_state["schedule_incomplete"] = outcome != "readback_confirmed"
                self.tariff_state["last_operation"] = self.client.schedule_operation
                self.tariff_state["clock_operation"] = self.client.clock_operation
                await self.tariff_store.async_save(self.tariff_state)
                self.async_update_listeners()
        await self.async_request_refresh()
        return result
