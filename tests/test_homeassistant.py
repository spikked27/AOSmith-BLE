"""Exercise HA flow/entity APIs on an installed Home Assistant runtime."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.water_heater import WaterHeaterEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.aosmith_ble.client import HeaterState
from custom_components.aosmith_ble.config_flow import ConfigFlow, is_heater, suggested_pin
from custom_components.aosmith_ble.const import DOMAIN, MODE, SERVICE_UUID, SETPOINT
from custom_components.aosmith_ble.diagnostics import async_get_config_entry_diagnostics
from custom_components.aosmith_ble.sensor import HeaterSensor
from custom_components.aosmith_ble.water_heater import Heater


@pytest.fixture
def coordinator():
    return SimpleNamespace(
        address="AA:BB:CC:DD:EE:FF",
        data=HeaterState(125, 4, 5, 0),
        last_update_success=True,
        async_set_value=AsyncMock(),
    )


async def test_entity_and_temperature_option(coordinator):
    heater = Heater(coordinator, SimpleNamespace(options={}))
    assert heater.target_temperature == 125
    assert heater.current_temperature is None
    assert heater.current_operation == "Hybrid"
    assert heater.supported_features == WaterHeaterEntityFeature.OPERATION_MODE
    await heater.async_set_operation_mode("Heat pump")
    coordinator.async_set_value.assert_awaited_once_with(MODE, 5)
    with pytest.raises(HomeAssistantError):
        await heater.async_set_temperature(temperature=120)
    heater = Heater(coordinator, SimpleNamespace(options={"enable_setpoint_writes": True}))
    await heater.async_set_temperature(temperature=120)
    coordinator.async_set_value.assert_awaited_with(SETPOINT, 0x30E4)
    with pytest.raises(HomeAssistantError):
        await heater.async_set_temperature(temperature=200)
    with pytest.raises(HomeAssistantError):
        await heater.async_set_operation_mode("Vacation")


def test_sensors_preserve_raw_units(coordinator):
    availability = HeaterSensor(coordinator, "availability")
    assert availability.native_value == 5
    assert availability.native_unit_of_measurement is None
    assert HeaterSensor(coordinator, "fault").native_value == 0
    setpoint = HeaterSensor(coordinator, "target_temperature")
    assert setpoint.native_value == 125
    assert setpoint.native_unit_of_measurement == "°F"
    assert setpoint.extra_state_attributes is None


def test_discovery_recognizes_name_or_service():
    assert is_heater(SimpleNamespace(name="icomm-example", service_uuids=[]))
    assert is_heater(SimpleNamespace(name="", service_uuids=[SERVICE_UUID.upper()]))
    assert not is_heater(SimpleNamespace(name="Other device", service_uuids=[]))


async def test_discovery_waits_for_uncached_advertisement(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    flow = ConfigFlow()
    flow.hass = hass
    info = SimpleNamespace(name="ICOMM-test", address="AA:BB:CC:DD:EE:FF", service_uuids=[])
    with (
        patch(
            "custom_components.aosmith_ble.config_flow.bluetooth.async_discovered_service_info",
            return_value=[],
        ),
        patch(
            "custom_components.aosmith_ble.config_flow.bluetooth.async_request_active_scan", None, create=True
        ),
        patch(
            "custom_components.aosmith_ble.config_flow.bluetooth.async_process_advertisements",
            AsyncMock(return_value=info),
        ) as wait,
    ):
        result = await flow.async_step_discover()
    assert result["step_id"] == "discover"
    assert result["data_schema"]({"address": info.address}) == {"address": info.address}
    wait.assert_awaited_once()
    await hass.async_stop()


async def test_empty_discovery_offers_retry_and_manual(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    flow = ConfigFlow()
    flow.hass = hass
    with (
        patch(
            "custom_components.aosmith_ble.config_flow.bluetooth.async_discovered_service_info",
            return_value=[],
        ),
        patch(
            "custom_components.aosmith_ble.config_flow.bluetooth.async_request_active_scan", None, create=True
        ),
        patch(
            "custom_components.aosmith_ble.config_flow.bluetooth.async_process_advertisements",
            AsyncMock(side_effect=TimeoutError),
        ),
    ):
        result = await flow.async_step_discover()
    assert result["type"] == "menu"
    assert result["step_id"] == "discovery_empty"
    assert set(result["menu_options"]) == {"discover", "manual"}
    await hass.async_stop()


async def test_modern_active_scan_refreshes_discovery(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    flow = ConfigFlow()
    flow.hass = hass
    info = SimpleNamespace(name="", address="AA:BB:CC:DD:EE:FF", service_uuids=[SERVICE_UUID])
    with (
        patch(
            "custom_components.aosmith_ble.config_flow.bluetooth.async_discovered_service_info",
            side_effect=[[], [info]],
        ),
        patch(
            "custom_components.aosmith_ble.config_flow.bluetooth.async_request_active_scan",
            AsyncMock(),
            create=True,
        ) as scan,
    ):
        result = await flow.async_step_discover()
    assert result["step_id"] == "discover"
    scan.assert_awaited_once_with(hass, duration=5)
    await hass.async_stop()


def test_pin_suggestions_do_not_use_shared_defaults():
    assert suggested_pin("ICOMM-AC000W012123456") == "123456"
    assert suggested_pin("ICOMM-unknown") == ""


async def test_existing_pairing_setup_never_enrolls(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    flow = ConfigFlow()
    flow.hass = hass
    flow._address = "AA:BB:CC:DD:EE:FF"
    result = await flow.async_step_credentials(
        {
            "pin": "123456",
            "pairing": "existing",
            "pairing_identifier": "HA0000000000000001",
        }
    )
    assert result["step_id"] == "confirm"
    client = SimpleNamespace(
        read_state=AsyncMock(return_value=HeaterState(125, 4, 5, 0)),
        enroll=AsyncMock(),
        disconnect=AsyncMock(),
        enrollment_attempted=False,
    )
    with patch("custom_components.aosmith_ble.config_flow.make_client", return_value=client):
        result = await flow.async_step_confirm({})
    assert result["type"] == "create_entry"
    assert result["data"]["pairing_identifier"] == "HA0000000000000001"
    client.enroll.assert_not_awaited()
    client.disconnect.assert_awaited_once()
    await hass.async_stop()


async def test_new_pairing_retry_does_not_duplicate_enrollment(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    flow = ConfigFlow()
    flow.hass = hass
    flow._address = "AA:BB:CC:DD:EE:FF"
    result = await flow.async_step_credentials({"pin": "123456", "pairing": "new"})
    generated = result["description_placeholders"]["identifier"]
    assert len(generated) == 18 and generated.startswith("HA")
    client = SimpleNamespace(
        enroll=AsyncMock(),
        read_state=AsyncMock(side_effect=TimeoutError),
        disconnect=AsyncMock(),
        enrollment_attempted=True,
    )
    with patch("custom_components.aosmith_ble.config_flow.make_client", return_value=client):
        result = await flow.async_step_confirm({})
        assert result["errors"]["base"] == "cannot_connect"
        client.read_state.side_effect = None
        client.read_state.return_value = HeaterState(125, 4, 5, 0)
        result = await flow.async_step_confirm({})
    assert result["type"] == "create_entry"
    assert result["data"]["pairing_identifier"] == generated
    client.enroll.assert_awaited_once()
    await hass.async_stop()


async def test_diagnostics_do_not_dump_entry_credentials(tmp_path, coordinator):
    hass = HomeAssistant(str(tmp_path))
    coordinator.client = SimpleNamespace(diagnostics=lambda: {"events": [], "connections": 2})
    hass.data[DOMAIN] = {"test_entry": coordinator}
    entry = SimpleNamespace(
        entry_id="test_entry", options={}, data={"pin": "123456", "pairing_identifier": "SECRET"}
    )
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    text = str(diagnostics)
    assert "SECRET" not in text and "123456" not in text
    assert coordinator.address not in text
    assert diagnostics["state"]["target_temperature"] == 125
    await hass.async_stop()
