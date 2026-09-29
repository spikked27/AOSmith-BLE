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
        options={},
        async_set_value=AsyncMock(),
    )


async def test_entity_and_temperature_option(coordinator):
    heater = Heater(coordinator, SimpleNamespace(options={"enable_setpoint_writes": False}))
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
        await heater.async_set_operation_mode("Unknown")


def test_sensors_preserve_raw_units(coordinator):
    availability = HeaterSensor(coordinator, "availability")
    assert availability.native_value is None
    assert availability.native_unit_of_measurement == "%"
    assert availability.extra_state_attributes["raw_value"] == 5
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


@pytest.mark.parametrize("temperature,mode", [(125, 4), (50, 2)])
async def test_existing_pairing_setup_never_enrolls(tmp_path, temperature, mode):
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
        read_state=AsyncMock(return_value=HeaterState(temperature, mode, 5, 0)),
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


async def test_default_temperature_controls_and_timed_selection(coordinator):
    heater = Heater(coordinator, SimpleNamespace(options={}))
    assert heater.supported_features & WaterHeaterEntityFeature.TARGET_TEMPERATURE
    await heater.async_set_operation_mode("Vacation")
    coordinator.async_set_value.assert_awaited_with(MODE, 0x6402)
    await heater.async_set_operation_mode("Guest")
    coordinator.async_set_value.assert_awaited_with(MODE, 0x0103)
    assert heater.current_temperature is None
    coordinator.data = HeaterState(125, 4, 5, 0, registers={"maximum_setpoint": 0x33AB})
    assert heater.max_temp == 125
    with pytest.raises(HomeAssistantError):
        await heater.async_set_temperature(temperature=126)


@pytest.mark.parametrize("maximum", [125, 140, 150])
async def test_temperature_limit_follows_device_up_to_documented_150(coordinator, maximum):
    from custom_components.aosmith_ble.protocol import encode_temperature

    heater = Heater(coordinator, SimpleNamespace(options={}))
    coordinator.data = HeaterState(125, 4, 5, 0, registers={"maximum_setpoint": encode_temperature(maximum)})
    assert heater.max_temp == maximum
    await heater.async_set_temperature(temperature=maximum)
    coordinator.async_set_value.assert_awaited_once_with(SETPOINT, encode_temperature(maximum))
    with pytest.raises(HomeAssistantError):
        await heater.async_set_temperature(temperature=maximum + 1)


def test_unknown_maximum_does_not_raise_fallback_to_150(coordinator):
    heater = Heater(coordinator, SimpleNamespace(options={}))
    assert heater.max_temp == 125
    coordinator.data = HeaterState(125, 4, 5, 0, registers={"maximum_setpoint": 0xFFFF})
    assert heater.max_temp == 125


async def test_maximum_is_read_even_when_diagnostics_are_disabled(tmp_path):
    from unittest.mock import Mock

    from custom_components.aosmith_ble.const import MAX_SETPOINT
    from custom_components.aosmith_ble.coordinator import HeaterCoordinator

    hass = HomeAssistant(str(tmp_path))
    client = SimpleNamespace(optional_registers={})
    entry = SimpleNamespace(
        data={"address": "AA:BB:CC:DD:EE:FF"},
        options={"extended_readings": False, "energy_readings": False},
        pref_disable_polling=False,
        async_on_unload=Mock(),
    )
    with patch("custom_components.aosmith_ble.coordinator.make_client", return_value=client):
        HeaterCoordinator(hass, entry)
    assert client.optional_registers == {"maximum_setpoint": MAX_SETPOINT}
    await hass.async_stop()


async def test_timed_mode_service_targets_only_selected_heater(tmp_path, coordinator):
    from custom_components.aosmith_ble.services import async_register_services

    hass = HomeAssistant(str(tmp_path))
    other = SimpleNamespace(async_set_value=AsyncMock())
    hass.data[DOMAIN] = {"first": coordinator, "other": other}
    async_register_services(hass)
    await hass.services.async_call(
        DOMAIN, "set_timed_mode", {"config_entry_id": "first", "mode": "Vacation", "days": 7}, blocking=True
    )
    coordinator.async_set_value.assert_awaited_once_with(MODE, 0x0702)
    other.async_set_value.assert_not_awaited()
    for data in [
        {"config_entry_id": "first", "mode": "Guest", "days": 8},
        {"config_entry_id": "missing", "mode": "Vacation", "days": 7},
    ]:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(DOMAIN, "set_timed_mode", data, blocking=True)
    assert coordinator.async_set_value.await_count == 1
    await hass.async_stop()


async def test_optional_entities_handle_missing_data_and_exact_values(coordinator):
    from custom_components.aosmith_ble.const import HOT_WATER_PLUS
    from custom_components.aosmith_ble.select import HotWaterPlus
    from custom_components.aosmith_ble.sensor import EnergySensor, ExtendedSensor

    boost = HotWaterPlus(coordinator)
    sensor = ExtendedSensor(coordinator, "vacation_days")
    energy = EnergySensor(coordinator)
    for entity in [boost, sensor, energy]:
        assert not entity.available
    assert energy.native_value is None
    coordinator.data = HeaterState(
        125,
        4,
        5,
        0,
        registers={
            "hot_water_plus": 2,
            "vacation_days": 100,
            "energy_wh": 350532,
        },
    )
    assert boost.current_option == "Level 2"
    assert sensor.native_value == 100 and sensor.native_unit_of_measurement is None
    assert energy.native_value == 350.532
    assert energy.native_unit_of_measurement == "kWh"
    assert energy.state_class == "total_increasing"
    await boost.async_select_option("Level 3")
    coordinator.async_set_value.assert_awaited_with(HOT_WATER_PLUS, 3)
    coordinator.data = HeaterState(125, 2, 5, 0, registers={"hot_water_plus": 2})
    with pytest.raises(HomeAssistantError):
        await boost.async_select_option("Off")


async def test_optional_platforms_respect_model_options(tmp_path, coordinator):
    from custom_components.aosmith_ble import PLATFORMS, select
    from custom_components.aosmith_ble.binary_sensor import FLAGS

    hass = HomeAssistant(str(tmp_path))
    hass.data[DOMAIN] = {"test": coordinator}
    entities = []
    entry = SimpleNamespace(entry_id="test", options={})
    await select.async_setup_entry(hass, entry, entities.extend)
    assert len(entities) == 1 and entities[0].name == "Mode duration"
    entities.clear()
    entry.options = {"enable_hot_water_plus": True}
    await select.async_setup_entry(hass, entry, entities.extend)
    assert len(entities) == 2
    assert "switch" not in PLATFORMS and set(FLAGS) == {"fault_present"}
    await hass.async_stop()


def test_action_ui_selectors_validate_with_minimum_ha_version():
    from pathlib import Path

    import yaml
    from homeassistant.helpers.selector import selector

    description = yaml.safe_load(Path("custom_components/aosmith_ble/services.yaml").read_text())
    fields = description["set_timed_mode"]["fields"]
    for field in fields.values():
        selector(field["selector"])


async def test_upgrade_retires_only_owned_demand_response_entities(tmp_path):
    from unittest.mock import MagicMock

    from homeassistant.helpers import entity_registry as er

    from custom_components.aosmith_ble import async_setup_entry

    hass = HomeAssistant(str(tmp_path))
    entry = SimpleNamespace(
        entry_id="test", options={}, async_on_unload=MagicMock(), add_update_listener=MagicMock()
    )
    registry = MagicMock()
    entities = [
        SimpleNamespace(
            platform=DOMAIN,
            unique_id="address_advanced_load_control",
            entity_id="switch.retired",
            disabled_by=None,
        ),
        SimpleNamespace(
            platform=DOMAIN,
            unique_id="address_cta_present",
            entity_id="binary_sensor.already_disabled",
            disabled_by=er.RegistryEntryDisabler.USER,
        ),
        SimpleNamespace(
            platform="another_integration",
            unique_id="address_advanced_load_control",
            entity_id="switch.unrelated",
            disabled_by=None,
        ),
        SimpleNamespace(
            platform=DOMAIN, unique_id="address_water_heater", entity_id="water_heater.keep", disabled_by=None
        ),
    ]
    coordinator = SimpleNamespace(
        async_config_entry_first_refresh=AsyncMock(), client=SimpleNamespace(disconnect=AsyncMock())
    )
    with (
        patch.object(er, "async_get", return_value=registry),
        patch.object(er, "async_entries_for_config_entry", return_value=entities),
        patch("custom_components.aosmith_ble.HeaterCoordinator", return_value=coordinator),
        patch.object(hass, "config_entries", SimpleNamespace(async_forward_entry_setups=AsyncMock())),
    ):
        assert await async_setup_entry(hass, entry)
    registry.async_update_entity.assert_called_once_with(
        "switch.retired", disabled_by=er.RegistryEntryDisabler.INTEGRATION
    )
    await hass.async_stop()


@pytest.mark.parametrize(
    "scale,expected", [("five_levels", 100), ("percent_used", 95), ("percent_remaining", 5)]
)
def test_availability_scale_is_explicit_and_keeps_raw_value(coordinator, scale, expected):
    coordinator.options = {"availability_scale": scale}
    sensor = HeaterSensor(coordinator, "availability")
    assert sensor.native_value == expected
    assert sensor.native_unit_of_measurement == "%"
    assert sensor.extra_state_attributes["raw_value"] == 5
    assert sensor.unique_id == coordinator.address + "_availability"
    assert sensor.state_class is None


async def test_reconnect_button_is_usable_when_heater_is_unavailable(coordinator):
    import asyncio

    from custom_components.aosmith_ble.button import DebugButton

    coordinator.last_update_success = False
    coordinator.command_lock = asyncio.Lock()
    coordinator.client = SimpleNamespace(disconnect=AsyncMock())
    coordinator.async_request_refresh = AsyncMock()
    button = DebugButton(coordinator, "reconnect")
    assert button.available
    await button.async_press()
    coordinator.client.disconnect.assert_awaited_once()
    coordinator.async_request_refresh.assert_awaited_once()


async def test_vacation_hides_temperature_editor_and_rejects_temperature_writes(coordinator):
    heater = Heater(coordinator, SimpleNamespace(options={}))
    coordinator.data = HeaterState(125, 2, 5, 0)
    assert not heater.supported_features & WaterHeaterEntityFeature.TARGET_TEMPERATURE
    with pytest.raises(HomeAssistantError, match="Leave Vacation"):
        await heater.async_set_temperature(temperature=120)
    coordinator.async_set_value.assert_not_awaited()
    await heater.async_set_operation_mode("Hybrid")
    coordinator.async_set_value.assert_awaited_once_with(MODE, 4)
    coordinator.data = HeaterState(125, 4, 5, 0)
    assert heater.supported_features & WaterHeaterEntityFeature.TARGET_TEMPERATURE
    for invalid in (None, "invalid", float("nan")):
        with pytest.raises(HomeAssistantError):
            await heater.async_set_temperature(temperature=invalid)


@pytest.mark.parametrize(
    "mode,key,days,option,encoded",
    [
        (2, "vacation_days", 100, "Until changed", 0x6402),
        (2, "vacation_days", 7, "7 days", 0x0702),
        (2, "vacation_days", 99, "99 days", 0x6302),
        (3, "guest_days", 1, "1 day", 0x0103),
        (3, "guest_days", 7, "7 days", 0x0703),
        (1, "electric_days", 0, "Until changed", 1),
        (1, "electric_days", 99, "99 days", 0x6301),
    ],
)
async def test_duration_device_control_reads_and_writes_active_mode(
    coordinator, mode, key, days, option, encoded
):
    from custom_components.aosmith_ble.select import ModeDuration

    coordinator.data = HeaterState(125, mode, 5, 0, registers={key: days})
    control = ModeDuration(coordinator)
    assert control.available
    assert control.current_option == option
    await control.async_select_option(option)
    coordinator.async_set_value.assert_awaited_once_with(MODE, encoded, expected_mode=mode)


async def test_duration_control_rejects_invalid_or_stale_values(coordinator):
    from custom_components.aosmith_ble.select import ModeDuration

    control = ModeDuration(coordinator)
    assert not control.available and control.current_option is None
    with pytest.raises(HomeAssistantError):
        await control.async_select_option("7 days")
    coordinator.data = HeaterState(125, 3, 5, 0, registers={"vacation_days": 100})
    assert control.available and control.current_option is None
    for option in ("8 days", "Until changed", "0 days", "7", None):
        with pytest.raises(HomeAssistantError):
            await control.async_select_option(option)
    coordinator.async_set_value.assert_not_awaited()
    coordinator.data = HeaterState(125, 2, 5, 0, registers={"vacation_days": 0xFFFF})
    assert control.current_option is None
    coordinator.last_update_success = False
    assert not control.available


@pytest.mark.parametrize(
    "raw,code,description,problem",
    [
        (0, 0, "No fault reported", False),
        (42, 42, "Clock not set", True),
        (31, 31, "Water leak detected", True),
        (80, 80, "Air filter needs cleaning", True),
        (0xAB2A, 42, "Clock not set", True),
        (255, 255, "Unknown heater fault (255)", True),
    ],
)
def test_single_error_indicator_decodes_clock_and_unknown_faults(
    coordinator, raw, code, description, problem
):
    from custom_components.aosmith_ble.binary_sensor import StatusSensor

    coordinator.data = HeaterState(125, 4, 5, raw)
    entity = StatusSensor(coordinator, "fault_present")
    assert entity.name == "Error status"
    assert entity.unique_id.endswith("_fault_present")
    assert entity.is_on is problem
    assert entity.extra_state_attributes["fault_code"] == code
    assert entity.extra_state_attributes["description"] == description
    assert entity.extra_state_attributes["clock_not_set"] is (code == 42)
    assert entity.extra_state_attributes["raw_fault_register"] == raw
    coordinator.last_update_success = False
    assert not entity.available
    assert entity.extra_state_attributes == {"description": "Heater status unavailable"}


async def test_tariff_removed_from_options_and_entity_setup(tmp_path, coordinator):
    from unittest.mock import PropertyMock

    from custom_components.aosmith_ble.config_flow import OptionsFlow
    from custom_components.aosmith_ble.sensor import async_setup_entry

    hass = HomeAssistant(str(tmp_path))
    entry = SimpleNamespace(
        entry_id="test",
        options={"tariff": {"old": "plan"}, "enable_utility_controls": True, "enable_setpoint_writes": False},
    )
    hass.data[DOMAIN] = {"test": coordinator}
    entities = []
    await async_setup_entry(hass, entry, entities.extend)
    assert not any(entity.unique_id.endswith(("_tariff", "_fault")) for entity in entities)
    flow = OptionsFlow()
    flow.hass = hass
    with patch.object(OptionsFlow, "config_entry", new_callable=PropertyMock, return_value=entry):
        form = await flow.async_step_init()
        assert form["type"] == "form" and form["step_id"] == "settings"
        result = await flow.async_step_settings({"poll_interval": 60})
        assert result["data"] == {"enable_setpoint_writes": False, "poll_interval": 60}
    await hass.async_stop()


async def test_upgrade_removes_tariff_cache_and_retires_duplicate_entities(tmp_path):
    from unittest.mock import MagicMock, call

    from homeassistant.helpers import entity_registry as er

    from custom_components.aosmith_ble import async_setup_entry

    hass = HomeAssistant(str(tmp_path))
    entry = SimpleNamespace(
        entry_id="test",
        options={"tariff": {"private": "plan"}, "enable_utility_controls": True, "poll_interval": 45},
        async_on_unload=MagicMock(),
        add_update_listener=MagicMock(),
    )
    registry = MagicMock()
    entities = [
        SimpleNamespace(
            platform=DOMAIN, unique_id="address_" + key, entity_id="sensor." + key, disabled_by=None
        )
        for key in ("tariff", "fault", "fault_present", "availability")
    ]
    config_entries = SimpleNamespace(async_forward_entry_setups=AsyncMock(), async_update_entry=MagicMock())
    coordinator = SimpleNamespace(
        async_config_entry_first_refresh=AsyncMock(), client=SimpleNamespace(disconnect=AsyncMock())
    )
    with (
        patch.object(er, "async_get", return_value=registry),
        patch.object(er, "async_entries_for_config_entry", return_value=entities),
        patch("custom_components.aosmith_ble.HeaterCoordinator", return_value=coordinator),
        patch.object(hass, "config_entries", config_entries),
    ):
        await async_setup_entry(hass, entry)
    config_entries.async_update_entry.assert_called_once_with(entry, options={"poll_interval": 45})
    assert registry.async_update_entity.call_args_list == [
        call("sensor.tariff", disabled_by=er.RegistryEntryDisabler.INTEGRATION),
        call("sensor.fault", disabled_by=er.RegistryEntryDisabler.INTEGRATION),
    ]
    await hass.async_stop()


async def test_failed_first_refresh_closes_client_and_leaves_no_loaded_entry(tmp_path):
    from unittest.mock import MagicMock

    from homeassistant.exceptions import ConfigEntryNotReady
    from homeassistant.helpers import entity_registry as er

    from custom_components.aosmith_ble import async_setup_entry

    hass = HomeAssistant(str(tmp_path))
    entry = SimpleNamespace(entry_id="test", options={})
    coordinator = SimpleNamespace(
        async_config_entry_first_refresh=AsyncMock(side_effect=ConfigEntryNotReady),
        client=SimpleNamespace(disconnect=AsyncMock()),
    )
    with (
        patch.object(er, "async_get", return_value=MagicMock()),
        patch.object(er, "async_entries_for_config_entry", return_value=[]),
        patch("custom_components.aosmith_ble.HeaterCoordinator", return_value=coordinator),
        pytest.raises(ConfigEntryNotReady),
    ):
        await async_setup_entry(hass, entry)
    coordinator.client.disconnect.assert_awaited_once()
    assert "test" not in hass.data.get(DOMAIN, {})
    await hass.async_stop()


def test_inactive_countdown_is_not_presented_as_current(coordinator):
    from custom_components.aosmith_ble.sensor import ExtendedSensor

    coordinator.data = HeaterState(125, 4, 5, 0, registers={"vacation_days": 100, "guest_days": 2})
    assert not ExtendedSensor(coordinator, "vacation_days").available
    assert not ExtendedSensor(coordinator, "guest_days").available
    coordinator.data = HeaterState(50, 2, 5, 0, registers={"vacation_days": 100, "guest_days": 2})
    assert ExtendedSensor(coordinator, "vacation_days").available
    assert not ExtendedSensor(coordinator, "guest_days").available


@pytest.mark.parametrize("raw,expected,category", [(0, 50, "Medium"), (5, 100, "High"), (1, None, "Unknown")])
def test_hps10_category_sensor_preserves_identity_and_uncertainty(coordinator, raw, expected, category):
    coordinator.options = {"availability_scale": "hps10_observed"}
    coordinator.data = HeaterState(125, 4, raw, 0)
    sensor = HeaterSensor(coordinator, "availability")
    assert sensor.native_value == expected
    assert sensor.extra_state_attributes["category"] == category
    assert sensor.extra_state_attributes["raw_value"] == raw
    assert sensor.unique_id == coordinator.address + "_availability"
    assert sensor.state_class is None
