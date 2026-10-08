"""Regression coverage for manual-only clock control and migration from 2.1.x."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed
from test_tariff_clock import PLAN, entry, make_pair, writes

from custom_components.aosmith_ble import async_migrate_entry
from custom_components.aosmith_ble.client import HeaterState
from custom_components.aosmith_ble.const import DOMAIN
from custom_components.aosmith_ble.coordinator import HeaterCoordinator


async def test_startup_fault_recovery_and_polling_never_write_clock(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    client = SimpleNamespace(
        optional_registers={},
        read_state=AsyncMock(return_value=HeaterState(125, 4, 5, 42)),
        read_clock=AsyncMock(return_value=(0, 0)),
        set_clock=AsyncMock(),
    )
    try:
        with patch("custom_components.aosmith_ble.coordinator.make_client", return_value=client):
            coordinator = HeaterCoordinator(hass, entry())
            await coordinator._async_update_data()
            client.read_state.side_effect = TimeoutError
            with pytest.raises(UpdateFailed):
                await coordinator._async_update_data()
            client.read_state.side_effect = None
            hass.config.time_zone = "America/New_York"
            await coordinator._async_update_data()
            await coordinator._async_update_data()
            client.read_clock.assert_not_awaited()
            client.set_clock.assert_not_awaited()
    finally:
        await hass.async_stop()


async def test_tariff_never_sets_clock_but_manual_button_does_and_persists(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    client, peripheral = make_pair()
    try:
        with patch("custom_components.aosmith_ble.coordinator.make_client", return_value=client):
            coordinator = HeaterCoordinator(hass, entry())
            coordinator.async_request_refresh = AsyncMock()
            result = await coordinator.async_apply_tariff(PLAN, "More Savings")
            assert result["outcome"] == "readback_confirmed"
            assert not any(packet[3] == 26 for packet in writes(peripheral))
            await coordinator.async_set_clock()
            assert len([packet for packet in writes(peripheral) if packet[3] == 26]) == 1
            history = await coordinator.clock.store.async_load()
            assert history["last_reason"] == "manual"
            assert history["automatic_setting_enabled"] is False
            assert history["last_operation"]["rtc_running_verified"] is False
    finally:
        await client.disconnect()
        await hass.async_stop()


@pytest.mark.parametrize(
    "disabled", [None, er.RegistryEntryDisabler.INTEGRATION, er.RegistryEntryDisabler.USER]
)
async def test_migration_restores_only_integration_disabled_clock_button(tmp_path, disabled):
    hass = HomeAssistant(str(tmp_path))
    test_entry = SimpleNamespace(entry_id="clock_test", version=1, minor_version=4, options={})
    registry = MagicMock()
    entity = SimpleNamespace(
        platform=DOMAIN,
        domain="button",
        unique_id="address_set_clock",
        entity_id="button.set_clock",
        disabled_by=disabled,
    )
    with (
        patch.object(er, "async_get", return_value=registry),
        patch.object(er, "async_entries_for_config_entry", return_value=[entity]),
        patch.object(hass, "config_entries", SimpleNamespace(async_update_entry=MagicMock())),
    ):
        await async_migrate_entry(hass, test_entry)
        if disabled == er.RegistryEntryDisabler.INTEGRATION:
            registry.async_update_entity.assert_called_once_with("button.set_clock", disabled_by=None)
        else:
            registry.async_update_entity.assert_not_called()
    await hass.async_stop()
