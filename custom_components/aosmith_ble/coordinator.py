"""Home Assistant Bluetooth adapter and polling coordinator."""

import asyncio
import logging
from datetime import timedelta

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import HeaterClient
from .const import CONF_IDENTIFIER, CONF_INTERVAL, CONF_PIN, DEFAULT_INTERVAL, NAME
from .protocol import ProtocolError

LOGGER = logging.getLogger(__name__)


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
        self.address = entry.data[CONF_ADDRESS]
        self.command_lock = asyncio.Lock()
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
            try:
                return await self.client.read_state()
            except (BleakError, TimeoutError, ProtocolError) as err:
                raise UpdateFailed(str(err)) from err

    async def async_set_value(self, register, value):
        async with self.command_lock:
            try:
                state = await self.client.set_value(register, value)
            except (BleakError, TimeoutError, ProtocolError) as err:
                self.async_set_update_error(UpdateFailed(str(err)))
                raise HomeAssistantError(str(err)) from err
            self.async_set_updated_data(state)
