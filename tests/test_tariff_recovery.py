"""Regressions for the owner's late-ACK tariff failure and matching stored tariff."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from test_tariff_clock import PLAN, entry, make_pair, writes

from custom_components.aosmith_ble.coordinator import HeaterCoordinator
from custom_components.aosmith_ble.schedule import build_schedule, season_words

CAPTURED = json.loads((Path(__file__).parent / "fixtures/dr_transition_20261007.json").read_text())[
    "schedule"
]


def populate(peripheral, schedule):
    for row in schedule["seasons"]:
        peripheral.registers.update({(row["block"], i): word for i, word in enumerate(season_words(row))})
    peripheral.registers.update({(28, 50 + i): word for i, word in enumerate(schedule["extra"]["words"])})


async def test_matching_owner_tariff_is_fully_confirmed_without_any_writes():
    client, peripheral = make_pair()
    populate(peripheral, CAPTURED)
    backup = AsyncMock()
    try:
        result = await client.apply_schedule(CAPTURED, backup)
        assert result["outcome"] == "readback_confirmed"
        assert result["already_current"] is True
        assert result["confirmed_chunks"] == 0
        assert not writes(peripheral)
        backup.assert_awaited_once()
        assert client.schedule_capture["complete"]
    finally:
        await client.disconnect()


async def test_observed_4_second_ack_is_awaited_before_sending_readback():
    client, peripheral = make_pair()
    client._timeout = 8
    original = peripheral.write_gatt_char
    accepted = asyncio.Event()
    delayed = None
    target = bytes([28, 68])

    async def delayed_ack():
        # Actual capture: write 03:04:31.099017, ACK 03:04:35.433172 UTC.
        await asyncio.sleep(4.334155)
        accepted.set()
        for _ in range(5):
            peripheral.send(bytes.fromhex("DB02071C4480D4"))

    async def heater(uuid, data, response):
        nonlocal delayed
        if data[:2] == b"\xbd\x40" and data[3:5] == target:
            peripheral.writes.append(data)
            for offset in range(6):
                peripheral.registers[(28, 68 + offset)] = 0
            delayed = asyncio.create_task(delayed_ack())
            return
        if data[:2] == b"\xbd\xa0" and data[3:5] == target and delayed is not None:
            assert accepted.is_set(), "Readback sent while the heater was still processing the write"
        await original(uuid, data, response)

    peripheral.write_gatt_char = heater
    try:
        result = await client.apply_schedule(build_schedule(PLAN, "More Savings"), AsyncMock())
        assert result["outcome"] == "readback_confirmed"
        assert sum(p[3:5] == target for p in writes(peripheral)) == 1
    finally:
        if delayed is not None and not delayed.done():
            delayed.cancel()
            await asyncio.gather(delayed, return_exceptions=True)
        await client.disconnect()


async def test_timeout_message_explains_phase_and_partial_result(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    client, peripheral = make_pair()

    async def fail(*args, **kwargs):
        client.schedule_operation = {
            "outcome": "partial_or_unconfirmed",
            "phase": "writing_holidays",
            "confirmed_chunks": 3,
            "last_register": [28, 68],
        }
        raise TimeoutError

    try:
        with patch("custom_components.aosmith_ble.coordinator.make_client", return_value=client):
            coordinator = HeaterCoordinator(hass, entry())
        with patch.object(client, "apply_schedule", side_effect=fail):
            with pytest.raises(HomeAssistantError) as error:
                await coordinator.async_apply_tariff(PLAN, "More Savings")
        assert "respond in time" in str(error.value)
        assert "holiday" in str(error.value)
        assert "incomplete" in str(error.value)
        assert str(error.value) != "HomeAssistantError"
        assert coordinator.tariff_state["last_operation"]["error_detail"] == str(error.value)
    finally:
        await client.disconnect()
        await hass.async_stop()


@pytest.mark.parametrize("recovers", [True, False])
async def test_initial_schedule_read_retries_once_on_new_session_without_writes(recovers):
    client, peripheral = make_pair()
    populate(peripheral, CAPTURED)
    original = peripheral.write_gatt_char
    attempts = 0

    async def interrupted(uuid, data, response):
        nonlocal attempts
        if data[:2] == b"\xbd\xa0" and data[3:5] == bytes([21, 0]):
            attempts += 1
            if attempts == 1 or not recovers:
                peripheral.writes.append(data)
                return
        await original(uuid, data, response)

    peripheral.write_gatt_char = interrupted
    try:
        if recovers:
            result = await client.apply_schedule(CAPTURED, AsyncMock())
            assert result["outcome"] == "readback_confirmed" and result["already_current"]
        else:
            with pytest.raises(TimeoutError):
                await client.apply_schedule(CAPTURED, AsyncMock())
            assert client.schedule_operation["outcome"] == "not_sent"
            assert not client.diagnostics()["connected"]
        assert attempts == 2 and client.connections == 2
        assert not writes(peripheral)
    finally:
        await client.disconnect()


@pytest.mark.parametrize("recovers", [True, False])
async def test_lost_chunk_readback_retries_read_only_and_never_replays_write(recovers):
    client, peripheral = make_pair()
    original = peripheral.write_gatt_char
    target = bytes([28, 50])
    attempts = 0
    sent = False

    async def interrupted(uuid, data, response):
        nonlocal attempts, sent
        if data[:2] == b"\xbd\x40" and data[3:5] == target:
            sent = True
        if sent and data[:2] == b"\xbd\xa0" and data[3:5] == target:
            attempts += 1
            if attempts == 1 or not recovers:
                peripheral.writes.append(data)
                return
        await original(uuid, data, response)

    peripheral.write_gatt_char = interrupted
    try:
        if recovers:
            result = await client.apply_schedule(build_schedule(PLAN, "More Savings"), AsyncMock())
            assert result["outcome"] == "readback_confirmed" and result["confirmed_chunks"] == 60
        else:
            with pytest.raises(TimeoutError):
                await client.apply_schedule(build_schedule(PLAN, "More Savings"), AsyncMock())
            assert client.schedule_operation["confirmed_chunks"] == 0
            assert len(writes(peripheral)) == 1
        assert attempts == 2 and client.connections == 2
        assert sum(p[3:5] == target for p in writes(peripheral)) == 1
    finally:
        await client.disconnect()


async def test_missing_write_ack_reconnects_for_readback_without_resending():
    client, peripheral = make_pair()
    original = peripheral.send

    def suppress_ack(packet):
        if packet[1] != 0x04:
            original(packet)

    peripheral.send = suppress_ack
    try:
        await client._ensure_session()
        record = {}
        async with client._lock:
            actual = await client._write_words_confirmed((28, 68), [0] * 6, record=record)
        assert actual == (0,) * 6
        assert client.connections == 2 and len(writes(peripheral)) == 1
        assert record["last_write"]["ack"].startswith("Not received")
    finally:
        await client.disconnect()


async def test_duplicate_read_data_cannot_satisfy_write_ack():
    client, peripheral = make_pair()
    original = peripheral.send
    accepted = asyncio.Event()
    handle = None

    def ack():
        accepted.set()
        original(bytes.fromhex("DB02071C4480D4"))

    def stale_data(packet):
        nonlocal handle
        if packet[1] == 0x04:
            original(bytes.fromhex("DB02131C440000000000000000000000008030"))
            handle = asyncio.get_running_loop().call_later(0.02, ack)
        else:
            original(packet)

    peripheral.send = stale_data
    try:
        await client._ensure_session()
        record = {}
        async with client._lock:
            await client._write_words_confirmed((28, 68), [0] * 6, record=record)
        assert accepted.is_set()
        assert record["last_write"]["ack"] == "DB02071C4480D4"
        assert len(writes(peripheral)) == 1
    finally:
        if handle:
            handle.cancel()
        await client.disconnect()


@pytest.mark.parametrize("changed", [(28, 75), (28, 78), (25, 61)])
async def test_noop_requires_every_schedule_and_extra_word_to_match(changed):
    client, peripheral = make_pair()
    populate(peripheral, CAPTURED)
    peripheral.registers[changed] ^= 1
    try:
        result = await client.apply_schedule(CAPTURED, AsyncMock())
        assert result["outcome"] == "readback_confirmed"
        assert result["confirmed_chunks"] == 60
        assert len(writes(peripheral)) == 60
        assert not result.get("already_current")
    finally:
        await client.disconnect()


async def test_matching_retry_clears_incomplete_status_and_preserves_backup(tmp_path):
    from copy import deepcopy

    hass = HomeAssistant(str(tmp_path))
    client, peripheral = make_pair()
    schedule = build_schedule(PLAN, "More Savings")
    populate(peripheral, schedule)
    try:
        with patch("custom_components.aosmith_ble.coordinator.make_client", return_value=client):
            coordinator = HeaterCoordinator(hass, entry())
        coordinator.async_request_refresh = AsyncMock()
        original_backup = {"kept": "original backup"}
        coordinator.tariff_state = {
            "original": deepcopy(original_backup),
            "schedule_incomplete": True,
            "last_operation": {"outcome": "partial_or_unconfirmed"},
        }
        result = await coordinator.async_apply_tariff(PLAN, "More Savings")
        assert result["already_current"]
        assert not writes(peripheral)
        assert coordinator.tariff_status == "Configured"
        assert coordinator.tariff_state["original"] == original_backup
        assert not coordinator.tariff_state["schedule_incomplete"]
        assert await coordinator.clock_guard._schedule() == schedule
        saved = await coordinator.tariff_store.async_load()
        assert saved["last_operation"]["outcome"] == "readback_confirmed"
        assert saved["applied_schedule"] == schedule
    finally:
        await client.disconnect()
        await hass.async_stop()
