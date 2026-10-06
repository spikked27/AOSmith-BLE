"""Tariff generation, interrupted uploads, clock packets, and HA completion UI."""

import asyncio
import json
import threading
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from test_client import IDENTIFIER, FakePeripheral, reply

from custom_components.aosmith_ble.client import HeaterClient
from custom_components.aosmith_ble.config_flow import OptionsFlow
from custom_components.aosmith_ble.const import DOMAIN, ENERGY_PREFERENCE, VERSION
from custom_components.aosmith_ble.coordinator import HeaterCoordinator
from custom_components.aosmith_ble.protocol import (
    ProtocolError,
    StatusError,
    decode_clock,
    encode_clock,
    read_frame,
    validate,
    write_words_frame,
)
from custom_components.aosmith_ble.schedule import build_schedule, decode_season, season_words
from custom_components.aosmith_ble.sensor import DiagnosticReadStatus, IntegrationVersion
from custom_components.aosmith_ble.tariff import TariffError, TariffLookup, cache_plan, validate_plan

ROOT = Path(__file__).resolve().parents[1]
INPUT = json.loads((ROOT / "research/rate195_illustrative_input.json").read_text())
EXPECTED = json.loads((ROOT / "research/rate195_illustrative_output.json").read_text())
PLAN = {"holidays": [], "touEvents": [{**e, "mode": 0, "modeData": 0} for e in INPUT["touEvents"]]}
LOCAL = datetime(2026, 10, 5, 19, 45, tzinfo=ZoneInfo("America/New_York"))


def make_pair():
    peripheral = FakePeripheral()
    peripheral.registers.update({(block, index): 0 for block in range(21, 26) for index in range(63)})
    peripheral.registers.update({(28, index): 0 for index in range(50, 79)})
    peripheral.registers.update({(26, 3): 0, (26, 4): 0})
    return HeaterClient(peripheral.connect, "123456", IDENTIFIER, timeout=0.1, spacing=0), peripheral


def writes(peripheral):
    return [packet for packet in peripheral.writes if packet[:2] == b"\xbd\x40"]


def test_owner_capture_rejects_register_but_packet_checksums_are_valid():
    assert read_frame(28, 113).hex().upper() == "BDA0071C710186"
    packet = bytes.fromhex("DB02071C7140DE")
    assert validate(packet) == packet
    assert packet[-2] == 0x40
    assert ENERGY_PREFERENCE == (28, 75)


@pytest.mark.parametrize("preference", list(EXPECTED["preferences"]))
def test_generated_schedule_matches_independently_recovered_fixture(preference):
    schedule = build_schedule(PLAN, preference)
    expected = EXPECTED["preferences"][preference]
    assert schedule["seasons"] == expected["season_blocks"]
    assert schedule["events"] == [{k: v for k, v in e.items() if k != "hex"} for e in expected["events"]]
    assert schedule["extra"]["words"][25:] == [expected["ble_preference_word"], 282, 307, 768]


def test_actual_rate195_schedule_matches_saved_seasons_but_not_preference_word():
    fixture = json.loads((ROOT / "research/observed_tariff_comparison.json").read_text())
    saved = fixture["saved_original"]
    generated = build_schedule(fixture["plans"]["195"], "More Savings")
    assert generated["seasons"] == saved["seasons"]
    # The separate word changed to More Hot Water while season bytes retained More Savings.
    assert generated["extra"]["words"][25] == 0
    assert saved["extra"]["words"][25] == 1
    assert generated["extra"]["words"][:25] == saved["extra"]["words"][:25]
    assert generated["extra"]["words"][26:] == saved["extra"]["words"][26:]
    candidate = build_schedule(fixture["plans"]["194"], "More Hot Water")
    assert candidate["seasons"] != saved["seasons"]
    events = decode_season(candidate["seasons"][0]["value"])["events"]
    assert [(e["hour"], e["days_of_week"], e["mode"]) for e in events] == [
        (12, 62, 9),
        (15, 62, 6),
        (19, 62, 0),
        (0, 65, 0),
    ]


def test_holiday_rules_and_unknown_holiday_are_not_silently_dropped():
    plan = deepcopy(PLAN)
    plan["holidays"] = [{"calendarEventId": n, "calendarEventName": str(n)} for n in (2, 12, 34)]
    assert build_schedule(plan, "More Savings")["extra"]["words"][:4] == [0x10C0, 0x7240, 0xB025, 0]
    plan["holidays"].append({"calendarEventId": 99999, "calendarEventName": "Unknown"})
    assert validate_plan(plan)["holidays"][-1]["calendarEventId"] == 99999
    with pytest.raises(ValueError, match="Unsupported holiday"):
        build_schedule(plan, "More Savings")


@pytest.mark.parametrize(
    "field,value",
    [("hour", 24), ("minute", -1), ("month", 13), ("fromDayOfWeek", True), ("rate", float("nan"))],
)
def test_invalid_api_events_are_rejected(field, value):
    plan = deepcopy(PLAN)
    plan["touEvents"][0][field] = value
    with pytest.raises(TariffError):
        validate_plan(plan)


def test_clock_preserves_local_fields_and_date_bits():
    local = datetime(2026, 10, 5, 18, 53, tzinfo=ZoneInfo("America/New_York"))
    assert encode_clock(local) == (0x3512, 0x3545)
    assert write_words_frame(26, 3, encode_clock(local))[:-1].hex().upper() == "BD400A1A0335123545"
    assert decode_clock(encode_clock(local)) == "2026-10-05T18:53"
    assert decode_clock((0, 0)) is None
    with pytest.raises(ValueError):
        encode_clock(local.replace(tzinfo=None))


async def test_clock_trial_sends_once_even_if_initial_candidate_is_unreadable():
    client, peripheral = make_pair()
    del peripheral.registers[(26, 3)]
    result = await client.set_clock(lambda: LOCAL)
    assert result["outcome"] == "readback_confirmed" and "before_error" in result
    assert len(writes(peripheral)) == 1
    assert result["after"] == list(encode_clock(LOCAL))
    assert result["rtc_running_verified"] is False


@pytest.mark.parametrize("behavior", ["reject", "mismatch", "disconnect"])
async def test_clock_failure_does_not_replay_write(behavior):
    client, peripheral = make_pair()
    original = peripheral.write_gatt_char

    async def respond(uuid, data, response):
        if data[1] == 0x40 and behavior == "reject":
            peripheral.writes.append(data)
            peripheral.send(reply(0x04, status=0x40))
            return
        await original(uuid, data, response)

    peripheral.write_gatt_char = respond
    peripheral.apply_write = behavior != "mismatch"
    peripheral.write_then_disconnect = behavior == "disconnect"
    with pytest.raises(Exception):
        await client.set_clock(lambda: LOCAL)
    assert len(writes(peripheral)) == 1
    assert client.clock_operation["outcome"] == "unconfirmed"


@pytest.mark.parametrize("ack", [None, 0x02, 0x04])
async def test_clock_confirms_fresh_readback_with_different_or_missing_ack(ack):
    client, peripheral = make_pair()
    send = peripheral.send

    def replace_ack(packet):
        if packet[1] == 0x04:
            if ack is not None:
                send(reply(ack))
            return
        send(packet)

    peripheral.send = replace_ack
    result = await client.set_clock(lambda: LOCAL)
    assert result["outcome"] == "readback_confirmed"
    assert result["after"] == list(encode_clock(LOCAL))
    assert len(writes(peripheral)) == 1
    assert any(e.get("frame", "").startswith("BD40") for e in result["traffic"])
    # An extended scan may evict the global ring; the command's evidence must survive.
    await client.inspect_registers({str(i): (26, 3) for i in range(35)})
    assert not any(e.get("frame", "").startswith("BD40") for e in client.events)
    assert any(e.get("frame", "").startswith("BD40") for e in client.clock_operation["traffic"])


async def test_clock_retains_actual_words_when_minutes_do_not_match():
    client, peripheral = make_pair()
    original = peripheral.write_gatt_char

    async def drop_minutes(uuid, data, response):
        await original(uuid, data, response)
        if data[1] == 0x40:
            peripheral.registers[(26, 3)] &= 0xFF

    peripheral.write_gatt_char = drop_minutes
    with pytest.raises(ProtocolError, match="Readback mismatch"):
        await client.set_clock(lambda: LOCAL)
    assert client.clock_operation["outcome"] == "unconfirmed"
    assert client.clock_operation["after"] == [LOCAL.hour, encode_clock(LOCAL)[1]]
    assert client.clock_operation["local_time"].endswith("19:00")
    assert len(writes(peripheral)) == 1


@pytest.mark.parametrize("echo", [b"", bytes((28, 75))])
async def test_delayed_empty_write_ack_cannot_satisfy_preference_read(echo):
    client, peripheral = make_pair()
    original = peripheral.write_gatt_char

    async def late_ack(uuid, data, response):
        if data[1] == 0xA0 and data[3:5] == bytes((28, 75)) and writes(peripheral):
            peripheral.send(reply(0x02, echo))
        await original(uuid, data, response)

    peripheral.write_gatt_char = late_ack
    result = await client.test_energy_preference(1, AsyncMock())
    assert result["outcome"] == "readback_confirmed" and result["after"] == 1
    assert len(writes(peripheral)) == 1
    assert any(e.get("frame", "").startswith("BD40") for e in result["traffic"])


async def test_extended_read_continues_after_owner_status_40():
    client, peripheral = make_pair()
    original = peripheral.write_gatt_char

    async def reject(uuid, data, response):
        if data[1] == 0xA0 and data[3:5] == bytes((28, 113)):
            peripheral.writes.append(data)
            peripheral.send(bytes.fromhex("DB02071C7140DE"))
            return
        await original(uuid, data, response)

    peripheral.write_gatt_char = reject
    result = await client.inspect_registers({"rejected": (28, 113), "clock": (26, 3), "mode": (11, 15)})
    assert "0x40" in result["registers"]["rejected"]["error"]
    assert result["registers"]["clock"]["raw"] == 0
    assert result["registers"]["mode"]["raw"] == 4
    assert not writes(peripheral)


async def test_full_upload_backs_up_before_writes_and_includes_all_twenty_slots():
    client, peripheral = make_pair()
    schedule = build_schedule(PLAN, "Most Savings")
    original_data = dict(peripheral.registers)
    saved = []

    async def backup(value):
        assert not writes(peripheral)
        saved.append(deepcopy(value))

    result = await client.apply_schedule(schedule, backup, local_now=lambda: LOCAL)
    assert result["outcome"] == "readback_confirmed" and result["confirmed_chunks"] == 60
    assert len(writes(peripheral)) == 61  # Clock + 5 extra-data + 55 season writes.
    for block in schedule["seasons"]:
        assert [peripheral.registers[(block["block"], i)] for i in range(62)] == season_words(block)
        assert any(p[3:5] == bytes((block["block"], 56)) for p in writes(peripheral))
    captured = await client.inspect_schedule()
    assert captured["complete"] and captured["seasons"][2]["decoded"] == decode_season(
        schedule["seasons"][2]["value"]
    )
    assert result["activation_verified"] is False
    await client.apply_schedule(saved[0], AsyncMock(), restoring=True)
    assert all(
        peripheral.registers[k] == v for k, v in original_data.items() if k[0] in (21, 22, 23, 24, 25, 28)
    )


async def test_backup_failure_prevents_clock_and_schedule_writes():
    client, peripheral = make_pair()
    with pytest.raises(OSError):
        await client.apply_schedule(
            build_schedule(PLAN, "More Hot Water"), AsyncMock(side_effect=OSError()), local_now=lambda: LOCAL
        )
    assert not writes(peripheral)


async def test_upload_stops_after_one_rejected_chunk_and_keeps_backup():
    client, peripheral = make_pair()
    original = peripheral.write_gatt_char

    async def reject(uuid, data, response):
        if data[1] == 0x40 and data[3:5] == bytes((21, 2)):
            peripheral.writes.append(data)
            peripheral.send(reply(0x04, status=0x40))
            return
        await original(uuid, data, response)

    peripheral.write_gatt_char = reject
    backup = AsyncMock()
    with pytest.raises(StatusError):
        await client.apply_schedule(build_schedule(PLAN, "More Hot Water"), backup)
    backup.assert_awaited_once()
    assert client.schedule_operation["confirmed_chunks"] == 6
    assert len(writes(peripheral)) == 7 and writes(peripheral)[-1][3:5] == bytes((21, 2))


async def test_missing_schedule_region_returns_read_errors_and_no_writes():
    client, peripheral = make_pair()
    del peripheral.registers[(23, 0)]
    capture = await client.inspect_schedule()
    assert not capture["complete"] and "23" in capture["errors"]
    assert len(capture["seasons"]) == 4
    with pytest.raises(ProtocolError, match="full existing schedule"):
        await client.apply_schedule(build_schedule(PLAN, "More Savings"), AsyncMock())
    assert not writes(peripheral)


async def test_anonymous_api_query_and_errors():
    response = MagicMock(status=200)
    response.json = AsyncMock(
        return_value={"data": {"utilitiesForZipcode": [{"lseId": 200, "name": "Utility"}]}}
    )
    manager = MagicMock(__aenter__=AsyncMock(return_value=response), __aexit__=AsyncMock(return_value=False))
    session = MagicMock()
    session.post.return_value = manager
    lookup = TariffLookup(session)
    assert await lookup.utilities("11704") == {"200": "Utility"}
    assert session.post.call_args.kwargs["json"]["variables"] == {"zipcode": "11704"}
    assert "authorization" not in {key.lower() for key in session.post.call_args.kwargs["headers"]}
    response.json.return_value = {"errors": [{"message": "Denied"}]}
    with pytest.raises(TariffError):
        await lookup.utilities("11704")


def entry():
    return ConfigEntry(
        entry_id="tariff_test",
        data={"address": "AA:BB:CC:DD:EE:FF"},
        options={},
        domain=DOMAIN,
        version=1,
        minor_version=2,
        title="Test heater",
        source="user",
        unique_id=None,
        discovery_keys={},
        subentries_data=None,
    )


@pytest.mark.parametrize("status,unread", [("Complete with errors", False), ("Incomplete", True)])
async def test_diagnostic_status_finishes_and_notifies_after_capture(tmp_path, status, unread):
    hass = HomeAssistant(str(tmp_path))
    rows = {
        "ok": {"raw": 0, "error": None},
        "bad": {"raw": None, "error": "Not read" if unread else "rejected"},
    }
    client = SimpleNamespace(
        optional_registers={}, inspect_registers=AsyncMock(return_value={"registers": rows})
    )
    with patch("custom_components.aosmith_ble.coordinator.make_client", return_value=client):
        coordinator = HeaterCoordinator(hass, entry())
        coordinator.async_request_refresh = AsyncMock()
        with patch(
            "custom_components.aosmith_ble.coordinator.persistent_notification.async_create"
        ) as notice:
            await coordinator.async_inspect_registers()
        assert DiagnosticReadStatus(coordinator).native_value == status
        assert coordinator.diagnostic_status["completed_at"] is not None
        assert "download diagnostics now" in notice.call_args.args[1]
        coordinator.installed_version = "1.4.0"
        version = IntegrationVersion(coordinator)
        assert version.native_value == VERSION and version.extra_state_attributes["restart_required"]
    await hass.async_stop()


async def test_options_menu_supplies_labels_without_frontend_translation_cache():
    menu = await OptionsFlow().async_step_init()
    assert menu["menu_options"] == {
        "settings": "Controls and readings",
        "tariff": "Find and apply a tariff",
        "remove_tariff": "Forget cached tariff",
    }


async def test_upload_task_is_cancelled_on_entry_unload(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    flow = OptionsFlow()
    flow.hass = hass
    flow._candidate = cache_plan(PLAN, "200", "Utility", "195", "195 Rate")
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def upload(*args, **kwargs):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    test_entry = entry()
    hass.data[DOMAIN] = {test_entry.entry_id: SimpleNamespace(async_apply_tariff=upload)}
    try:
        with patch.object(OptionsFlow, "config_entry", new_callable=PropertyMock, return_value=test_entry):
            await flow.async_step_tariff_confirm({"preference": "More Savings", "sync_clock": False})
            await asyncio.wait_for(started.wait(), 1)
            await asyncio.wait_for(hass.async_block_till_done(), 1)
            await test_entry._async_process_on_unload(hass)
            assert cancelled.is_set(), "The upload must stop when the integration unloads"
            result = await flow.async_step_tariff_apply()
            assert result["type"] == "progress_done"
            result = await flow.async_step_tariff_result()
            assert result["errors"]["base"] == "tariff_apply_failed"
            assert "interrupted" in result["description_placeholders"]["detail"].lower()
    finally:
        if flow._upload_task and not flow._upload_task.done():
            flow._upload_task.cancel()
        if flow._upload_task:
            await asyncio.gather(flow._upload_task, return_exceptions=True)
        await hass.async_stop()


async def test_ha_shutdown_cancels_partial_upload_and_preserves_backup(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    client, peripheral = make_pair()
    client._timeout = 10
    sent = asyncio.Event()
    original_write = peripheral.write_gatt_char

    async def pause_after_write(uuid, data, response):
        await original_write(uuid, data, response)
        if data[1] == 0x40:
            sent.set()
            await asyncio.Event().wait()

    peripheral.write_gatt_char = pause_after_write
    test_entry = entry()
    loop_thread = threading.get_ident()

    def compile_off_loop(*args):
        assert threading.get_ident() != loop_thread
        return build_schedule(*args)

    with (
        patch("custom_components.aosmith_ble.coordinator.make_client", return_value=client),
        patch("custom_components.aosmith_ble.coordinator.build_schedule", side_effect=compile_off_loop),
    ):
        coordinator = HeaterCoordinator(hass, test_entry)
        coordinator.async_request_refresh = AsyncMock()

        async def stop(_event):
            await client.disconnect()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop)
        task = test_entry.async_create_background_task(
            hass,
            coordinator.async_apply_tariff(PLAN, "More Savings", sync_clock=False),
            "test_upload",
        )
        try:
            await asyncio.wait_for(sent.wait(), 2)
            await asyncio.wait_for(hass.async_stop(force=True), 2)
            assert task.cancelled()
            assert not client._lock.locked() and not coordinator.command_lock.locked()
            assert not peripheral.is_connected
            assert len(writes(peripheral)) == 1
            saved = json.loads(Path(coordinator.tariff_store.path).read_text())["data"]
            assert saved["original"]["complete"]
            assert saved["last_operation"]["interrupted"]
            assert saved["last_operation"]["outcome"] == "partial_or_unconfirmed"
            assert saved["last_operation"]["phase"] == "writing_holidays"
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("count", [21, 101])
def test_oversized_tariff_is_rejected_before_expensive_generation(count):
    plan = {"holidays": [], "touEvents": [dict(PLAN["touEvents"][0])] * count}
    with patch("custom_components.aosmith_ble.schedule.make_events") as generator:
        with pytest.raises((TariffError, ValueError), match="capacity|event slots"):
            build_schedule(plan, "More Savings")
        generator.assert_not_called()


async def test_tariff_backup_survives_restart_and_is_not_replaced(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    client, peripheral = make_pair()
    test_entry = entry()
    with patch("custom_components.aosmith_ble.coordinator.make_client", return_value=client):
        first = HeaterCoordinator(hass, test_entry)
        first.async_request_refresh = AsyncMock()
        await first.async_apply_tariff(PLAN, "Most Savings", sync_clock=False)
        original = deepcopy(first.tariff_state["original"])
        await first.async_apply_tariff(PLAN, "More Hot Water", sync_clock=False)
        assert first.tariff_state["original"] == original
        second = HeaterCoordinator(hass, test_entry)
        second.async_request_refresh = AsyncMock()
        await second.async_apply_tariff(restore=True)
        assert second.tariff_state["original"] == original
        assert peripheral.registers[(28, 75)] == 0
    await hass.async_stop()


@pytest.mark.parametrize("outcome", ["readback_confirmed", "raises", "partial_or_unconfirmed", None])
async def test_tariff_options_use_progress_and_save_only_confirmed_upload(tmp_path, outcome):
    hass = HomeAssistant(str(tmp_path))
    flow = OptionsFlow()
    flow.hass = hass
    flow._candidate = cache_plan(PLAN, "200", "Utility", "195", "195 Rate")
    waiter = asyncio.Event()

    async def upload(*args, **kwargs):
        await waiter.wait()
        if outcome == "raises":
            raise HomeAssistantError("Readback failed")
        return {"outcome": outcome} if outcome else None

    coordinator = SimpleNamespace(async_apply_tariff=upload)
    test_entry = entry()
    hass.data[DOMAIN] = {test_entry.entry_id: coordinator}
    with patch.object(OptionsFlow, "config_entry", new_callable=PropertyMock, return_value=test_entry):
        result = await flow.async_step_tariff_confirm({"preference": "More Savings", "sync_clock": True})
        assert result["type"] == "progress"
        waiter.set()
        try:
            await flow._upload_task
        except HomeAssistantError:
            pass
        result = await flow.async_step_tariff_apply()
        assert result["type"] == "progress_done"
        result = await flow.async_step_tariff_result()
        if outcome != "readback_confirmed":
            assert result["errors"]["base"] == "tariff_apply_failed"
            detail = result["description_placeholders"]["detail"]
            assert detail
            # A browser refresh or duplicate progress callback must not turn failure into success.
            result = await flow.async_step_tariff_result()
            assert result["type"] == "form"
            assert result["errors"]["base"] == "tariff_apply_failed"
            assert result["description_placeholders"]["detail"] == detail
            coordinator.async_apply_tariff = AsyncMock(return_value={"outcome": "readback_confirmed"})
            await flow.async_step_tariff_confirm({"preference": "More Hot Water", "sync_clock": False})
            await flow._upload_task
            await flow.async_step_tariff_apply()
            result = await flow.async_step_tariff_result()
            assert result["type"] == "create_entry"
            assert result["data"]["tariff_preference"] == "More Hot Water"
        else:
            assert result["type"] == "create_entry"
            assert result["data"]["tariff"]["tariff_id"] == "195"
            assert result["data"]["tariff_preference"] == "More Savings"
    await hass.async_stop()
