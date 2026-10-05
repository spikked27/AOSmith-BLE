"""Discovery, explicit enrollment, reuse, and polling options."""

import re
import secrets

import voluptuous as vol
from bleak.exc import BleakError
from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback

from .const import (
    CONF_ENERGY_PREFERENCE,
    CONF_IDENTIFIER,
    CONF_INTERVAL,
    CONF_PIN,
    DEFAULT_INTERVAL,
    DOMAIN,
    SERVICE_UUID,
    clean_options,
)
from .coordinator import make_client
from .protocol import ProtocolError, StatusError, validate_identifier


def suggested_pin(name):
    candidate = name[-6:] if len(name) <= 21 else name[15:-4]
    return candidate if len(candidate) == 6 and candidate.isascii() and candidate.isdigit() else ""


def is_heater(info):
    names = (info.name or "", getattr(getattr(info, "device", None), "name", "") or "")
    return any(name.upper().startswith("ICOMM-") for name in names) or SERVICE_UUID in {
        uuid.lower() for uuid in info.service_uuids
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self):
        self._address = ""
        self._name = ""
        self._data = {}
        self._identifier = "HA" + secrets.token_hex(8)
        self._new_pairing = True
        self._enroll_attempted = False

    async def async_step_bluetooth(self, discovery_info):
        self._address = discovery_info.address.upper()
        self._name = discovery_info.name or ""
        await self.async_set_unique_id(self._address)
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {"name": self._name or self._address}
        return await self.async_step_credentials()

    async def async_step_user(self, user_input=None):
        return self.async_show_menu(step_id="user", menu_options=["discover", "manual"])

    async def async_step_discover(self, user_input=None):
        if user_input:
            self._address = user_input[CONF_ADDRESS].upper()
            info = bluetooth.async_last_service_info(self.hass, self._address, connectable=True)
            self._name = info.name if info and info.name else ""
            await self.async_set_unique_id(self._address)
            self._abort_if_unique_id_configured()
            return await self.async_step_credentials()

        def cached_devices():
            return {
                info.address.upper(): f"{info.name or 'iCOMM'} ({info.address})"
                for info in bluetooth.async_discovered_service_info(self.hass, connectable=True)
                if is_heater(info)
            }

        devices = cached_devices()
        if not devices:
            # Newer HA can explicitly request a short active scan. Older supported
            # versions can wait for the shared scanner without creating another one.
            active_scan = getattr(bluetooth, "async_request_active_scan", None)
            if active_scan is not None:
                await active_scan(self.hass, duration=5)
                devices = cached_devices()
            else:
                try:
                    info = await bluetooth.async_process_advertisements(
                        self.hass,
                        is_heater,
                        {"connectable": True},
                        bluetooth.BluetoothScanningMode.ACTIVE,
                        5,
                    )
                    devices = cached_devices()
                    devices[info.address.upper()] = f"{info.name or 'iCOMM'} ({info.address})"
                except TimeoutError:
                    devices = cached_devices()
        if not devices:
            return self.async_show_menu(
                step_id="discovery_empty",
                menu_options=["discover", "manual"],
            )
        return self.async_show_form(
            step_id="discover",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(devices),
                }
            ),
        )

    async def async_step_manual(self, user_input=None):
        errors = {}
        if user_input:
            address = user_input[CONF_ADDRESS].strip().upper()
            if not re.fullmatch(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", address):
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                self._address = address
                info = bluetooth.async_last_service_info(self.hass, address, connectable=True)
                self._name = info.name if info and info.name else ""
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()
                return await self.async_step_credentials()
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): str,
                }
            ),
            errors=errors,
        )

    async def async_step_credentials(self, user_input=None):
        errors = {}
        if user_input:
            pin = user_input[CONF_PIN].strip()
            identifier = user_input.get(CONF_IDENTIFIER, "").strip() or self._identifier
            reuse = user_input["pairing"] == "existing"
            if len(pin) != 6 or not pin.isascii() or not pin.isdigit():
                errors[CONF_PIN] = "invalid_pin"
            try:
                validate_identifier(identifier)
            except ValueError:
                errors[CONF_IDENTIFIER] = "invalid_identifier"
            if reuse and not user_input.get(CONF_IDENTIFIER, "").strip():
                errors[CONF_IDENTIFIER] = "identifier_required"
            if not errors:
                self._new_pairing = not reuse
                self._identifier = identifier
                self._data = {CONF_ADDRESS: self._address, CONF_PIN: pin, CONF_IDENTIFIER: identifier}
                return await self.async_step_confirm()
        return self.async_show_form(
            step_id="credentials",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PIN, default=suggested_pin(self._name)): str,
                    vol.Required("pairing", default="new"): vol.In(
                        {
                            "new": "Create a new local pairing",
                            "existing": "Reuse an existing local pairing",
                        }
                    ),
                    vol.Optional(CONF_IDENTIFIER, default=""): str,
                }
            ),
            errors=errors,
            description_placeholders={"name": self._name or self._address},
        )

    async def async_step_confirm(self, user_input=None):
        errors = {}
        if user_input is not None:
            client = make_client(self.hass, self._data)
            try:
                if self._new_pairing and not self._enroll_attempted:
                    await client.enroll()
                state = await client.read_state()
                minimum = 50 if state.mode == 2 else 90
                if not (minimum <= state.target_temperature <= 180 and 1 <= state.mode <= 5):
                    errors["base"] = "unsupported_profile"
                else:
                    return self.async_create_entry(
                        title=self._name or "AO Smith water heater", data=self._data
                    )
            except StatusError as err:
                errors["base"] = "pairing_full" if err.code == 4 else "authentication_failed"
            except (BleakError, TimeoutError):
                errors["base"] = "cannot_connect"
            except ProtocolError:
                errors["base"] = "invalid_response"
            finally:
                self._enroll_attempted |= client.enrollment_attempted
                await client.disconnect()
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={
                "identifier": self._identifier,
                "action": "Create one pairing"
                if self._new_pairing and not self._enroll_attempted
                else "Reuse pairing",
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlow()


class OptionsFlow(config_entries.OptionsFlow):
    def _save(self, updates):
        options = clean_options({**self.config_entry.options, **updates})
        return self.async_create_entry(title="", data=options)

    async def async_step_init(self, user_input=None):
        return await self.async_step_settings(user_input)

    async def async_step_settings(self, user_input=None):
        if user_input is not None:
            return self._save(user_input)
        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_INTERVAL, default=self.config_entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL)
                    ): vol.All(vol.Coerce(int), vol.Range(min=15, max=300)),
                    vol.Required(
                        "enable_hot_water_plus",
                        default=self.config_entry.options.get("enable_hot_water_plus", False),
                    ): bool,
                    vol.Required(
                        CONF_ENERGY_PREFERENCE,
                        default=self.config_entry.options.get(CONF_ENERGY_PREFERENCE, False),
                    ): bool,
                }
            ),
        )
