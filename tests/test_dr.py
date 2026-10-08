"""Read-only capture packets, unknown offsets, history, cancellation and bounded monitoring."""

import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from test_tariff_clock import entry, make_pair, writes

from custom_components.aosmith_ble.const import DOMAIN, INSPECT_REGISTERS
from custom_components.aosmith_ble.coordinator import HeaterCoordinator
from custom_components.aosmith_ble.dr import HISTORY_LIMIT, DRMonitor
from custom_components.aosmith_ble.services import async_register_services


def populate(peripheral):
    peripheral.registers.update({(27, i): i for i in range(26)})
    peripheral.registers.update({reg: 0 for reg in INSPECT_REGISTERS.values() if reg != (28, 113)})


async def test_capture_reads_complete_allowlist_with_timestamps_and_never_writes():
    client, peripheral = make_pair()
    populate(peripheral)
    try:
        result = await client.inspect_dr_status()
        assert result["complete"]
        assert result["active_dr_level"] is None
        assert {f"27:{i}" for i in range(26)} <= result["registers"].keys()
        assert result["registers"]["27:0"]["name"] == "unmapped_status"
        assert "28:113" not in result["registers"]
        assert all(row["read_at"] and row["error"] is None for row in result["registers"].values())
        assert not writes(peripheral)
        assert not any(packet[:2] == b"\xbd\xf0" for packet in peripheral.writes)
    finally:
        await client.disconnect()


async def test_rejected_word_does_not_hide_other_status_words():
    client, peripheral = make_pair()
    populate(peripheral)
    del peripheral.registers[(27, 0)]
    try:
        result = await client.inspect_dr_status()
        assert not result["complete"]
        assert result["registers"]["27:0"]["raw"] is None
        assert result["registers"]["27:1"]["raw"] == 1
        assert result["registers"]["26:4"]["read_at"]
        assert not writes(peripheral)
    finally:
        await client.disconnect()


async def test_transport_failure_keeps_partial_capture_and_stops_reads():
    client, peripheral = make_pair()
    populate(peripheral)
    read = client._read

    async def fail(reg):
        if reg == (27, 2):
            raise TimeoutError
        return await read(reg)

    try:
        with patch.object(client, "_read", side_effect=fail) as mocked:
            result = await client.inspect_dr_status()
        assert result["error"] == "TimeoutError"
        assert result["registers"]["27:1"]["raw"] == 1
        assert result["registers"]["27:3"]["read_at"] is None
        assert mocked.await_count == 3
        assert not client.diagnostics()["connected"]
        assert not writes(peripheral)
    finally:
        await client.disconnect()


@pytest.fixture
async def setup_dr(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    client, peripheral = make_pair()
    populate(peripheral)
    with patch("custom_components.aosmith_ble.coordinator.make_client", return_value=client):
        coordinator = HeaterCoordinator(hass, entry())
    await coordinator.clock.async_load()
    coordinator.async_update_listeners = lambda: None
    try:
        yield hass, coordinator, client, peripheral
    finally:
        await coordinator.dr.async_stop()
        await client.disconnect()
        await hass.async_stop()


async def test_persistent_history_compares_changes_and_bounds_memory(setup_dr):
    hass, coordinator, client, peripheral = setup_dr
    first = await coordinator.dr.async_capture()
    peripheral.registers[(27, 0)] = 7
    second = await coordinator.dr.async_capture()
    assert second["changes_since_previous"]["27:0"] == {"before": 0, "after": 7, "name": "unmapped_status"}
    assert second["compared_to"] == first["started_at"]
    del peripheral.registers[(27, 0)]
    third = await coordinator.dr.async_capture()
    assert "27:0" not in third["changes_since_previous"]
    coordinator.dr.data["captures"] = [deepcopy(first) for _ in range(HISTORY_LIMIT)]
    await coordinator.dr.async_capture()
    restored = DRMonitor(hass, coordinator)
    await restored.async_load()
    assert len(restored.data["captures"]) == HISTORY_LIMIT
    assert restored.data["captures"][-1]["registers"]["27:0"]["raw"] is None
    assert not writes(peripheral)


async def test_monitor_deadline_duplicate_start_and_stop(setup_dr):
    _, coordinator, _, peripheral = setup_dr
    now = [0.0]
    real_sleep = asyncio.sleep

    async def advance(delay):
        now[0] += delay
        await real_sleep(0)

    with (
        patch("custom_components.aosmith_ble.dr.monotonic", side_effect=lambda: now[0]),
        patch("custom_components.aosmith_ble.dr.asyncio.sleep", side_effect=advance),
        patch("custom_components.aosmith_ble.dr.persistent_notification.async_create"),
    ):
        await coordinator.dr.async_start(2)
        with pytest.raises(HomeAssistantError, match="already"):
            await coordinator.dr.async_start(2)
        await coordinator.dr.task
    assert coordinator.dr.data["status"] == "Complete"
    assert coordinator.dr.data["session_captures"] == 2
    assert not writes(peripheral)
    await coordinator.dr.async_start(180)
    await coordinator.dr.async_stop()
    assert coordinator.dr.task.done()
    assert coordinator.dr.data["status"] == "Stopped"


async def test_loaded_running_session_is_interrupted_not_resumed(setup_dr):
    hass, coordinator, _, _ = setup_dr
    await coordinator.dr.store.async_save({"status": "Monitoring", "captures": []})
    restored = DRMonitor(hass, coordinator)
    await restored.async_load()
    assert restored.data["status"] == "Interrupted by restart"
    assert restored.task is None


async def test_dr_services_target_selected_heater_and_validate_duration(setup_dr):
    hass, coordinator, _, _ = setup_dr
    coordinator.dr.async_start = AsyncMock()
    coordinator.dr.async_stop = AsyncMock()
    coordinator.async_capture_dr_status = AsyncMock()
    hass.data[DOMAIN] = {"chosen": coordinator}
    async_register_services(hass)
    await hass.services.async_call(DOMAIN, "start_dr_monitor", {"config_entry_id": "chosen"}, blocking=True)
    coordinator.dr.async_start.assert_awaited_once_with(180)
    await hass.services.async_call(DOMAIN, "capture_dr_status", {"config_entry_id": "chosen"}, blocking=True)
    coordinator.async_capture_dr_status.assert_awaited_once()
    for data in ({"config_entry_id": "missing"}, {"config_entry_id": "chosen", "duration_minutes": 0}):
        with pytest.raises((HomeAssistantError, vol.Invalid)):
            await hass.services.async_call(DOMAIN, "start_dr_monitor", data, blocking=True)


async def test_stop_during_ble_read_releases_connection_and_command_lock(setup_dr):
    _, coordinator, client, peripheral = setup_dr
    reading = asyncio.Event()

    async def slow_read(reg):
        reading.set()
        await asyncio.Future()

    with patch.object(client, "_read", side_effect=slow_read):
        await coordinator.dr.async_start(180)
        await asyncio.wait_for(reading.wait(), 1)
        await asyncio.wait_for(coordinator.dr.async_stop(), 1)
    assert not coordinator.command_lock.locked()
    assert not client.diagnostics()["connected"]
    assert (await coordinator.dr.store.async_load())["status"] == "Stopped"
    await client.read_state()
    assert client.diagnostics()["connected"]
    assert not writes(peripheral)


async def test_expired_capture_waiting_for_command_lock_sends_no_reads(setup_dr):
    _, coordinator, client, _ = setup_dr
    with patch.object(client, "inspect_dr_status", new_callable=AsyncMock) as capture:
        result = await coordinator.dr.async_capture(source="monitor", deadline=-1)
    assert result is None
    capture.assert_not_awaited()
