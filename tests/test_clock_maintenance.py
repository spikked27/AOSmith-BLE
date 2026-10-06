"""Automatic clock comparisons, drift correction, lifecycle and durable retry limits."""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from test_tariff_clock import entry, make_pair, writes

from custom_components.aosmith_ble.client import HeaterState
from custom_components.aosmith_ble.clock import ClockMaintenance, correction_reason, elapsed, next_hour_check
from custom_components.aosmith_ble.coordinator import HeaterCoordinator
from custom_components.aosmith_ble.protocol import ProtocolError, encode_clock

LOCAL = datetime(2026, 10, 5, 21, 35, tzinfo=ZoneInfo("America/New_York"))
CONTEXT = {"time_zone": "America/New_York", "utc_offset": -14400}


def synced(now=LOCAL):
    return {"last_synced_at": now.isoformat(), "sync_context": CONTEXT}


@pytest.mark.parametrize(
    "minutes,reason", [(0, None), (2, None), (-2, None), (3, "clock_drift"), (-3, "clock_drift")]
)
def test_full_minutes_allow_two_minutes_of_drift(minutes, reason):
    assert correction_reason(encode_clock(LOCAL + timedelta(minutes=minutes)), LOCAL, {}, CONTEXT) == reason


@pytest.mark.parametrize("minute", [0, 1, 30, 59])
def test_zero_minute_readback_does_not_mean_large_drift(minute):
    now = LOCAL.replace(minute=minute)
    assert correction_reason(encode_clock(now.replace(minute=0)), now, synced(now), CONTEXT) is None


@pytest.mark.parametrize(
    "offset,reason", [(1, None), (2, "date_or_hour_mismatch"), (15, "date_or_hour_mismatch")]
)
def test_hour_and_midnight_boundary_grace(offset, reason):
    now = LOCAL.replace(hour=0, minute=offset)
    previous_hour = now.replace(minute=0) - timedelta(hours=1)
    assert correction_reason(encode_clock(previous_hour), now, synced(now), CONTEXT) == reason


def test_partial_readback_refreshes_daily_and_initializes_invalid_clock():
    partial = encode_clock(LOCAL.replace(minute=0))
    assert correction_reason(partial, LOCAL, {}, CONTEXT) == "daily_refresh_partial_readback"
    assert (
        correction_reason(partial, LOCAL, synced(LOCAL - timedelta(hours=24)), CONTEXT)
        == "daily_refresh_partial_readback"
    )
    assert correction_reason((0, 0), LOCAL, {}, CONTEXT) == "invalid_clock"
    assert (
        correction_reason(encode_clock(LOCAL), LOCAL, {}, CONTEXT, clock_unset=True) == "heater_clock_unset"
    )


@pytest.mark.parametrize(
    "now",
    [
        datetime(2026, 3, 8, 3, 5, tzinfo=ZoneInfo("America/New_York")),
        datetime(2026, 11, 1, 1, 35, fold=1, tzinfo=ZoneInfo("America/New_York")),
    ],
)
def test_dst_compares_offsets_even_when_wall_clock_matches(now):
    context = {**CONTEXT, "utc_offset": int(now.utcoffset().total_seconds())}
    before = {**context, "utc_offset": -18000 if context["utc_offset"] == -14400 else -14400}
    assert (
        correction_reason(encode_clock(now), now, {"sync_context": before}, context)
        == "timezone_or_dst_changed"
    )
    first = datetime(2026, 11, 1, 1, 35, fold=0, tzinfo=ZoneInfo("America/New_York"))
    second = first.replace(fold=1)
    assert elapsed(second, first.isoformat()) == 3600


def test_timezone_change_and_backwards_host_correction():
    assert (
        correction_reason(
            encode_clock(LOCAL), LOCAL, {"sync_context": CONTEXT}, {**CONTEXT, "time_zone": "America/Toronto"}
        )
        == "timezone_or_dst_changed"
    )
    assert elapsed(LOCAL, (LOCAL + timedelta(hours=1)).isoformat()) is None
    assert elapsed(LOCAL, "invalid") is None


@pytest.fixture
async def setup_clock(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    hass.config.time_zone = "America/New_York"
    now = [LOCAL]
    client = SimpleNamespace(read_clock=AsyncMock(), clock_operation=None)
    client.read_clock.return_value = encode_clock(LOCAL.replace(minute=0))

    async def set_clock(local_now):
        local = local_now()
        client.clock_operation = {
            "time": local.isoformat(),
            "requested_words": list(encode_clock(local)),
            "outcome": "acknowledged",
            "readback_scope": "date_and_hour",
        }
        return client.clock_operation

    client.set_clock = AsyncMock(side_effect=set_clock)
    manager = ClockMaintenance(hass, entry(), client, lambda: now[0])
    yield hass, client, manager, now
    await hass.async_stop()


async def test_startup_periodic_and_daily_refresh_without_write_loop(setup_clock):
    hass, client, manager, now = setup_clock
    await manager.async_check(0)
    assert client.set_clock.await_count == 1
    for _ in range(3):
        await manager.async_check(0)
    assert client.read_clock.await_count == 1
    now[0] = LOCAL.replace(hour=22, minute=1, second=59)
    await manager.async_check(0)
    assert client.read_clock.await_count == 1
    now[0] += timedelta(seconds=1)
    client.read_clock.return_value = encode_clock(now[0].replace(minute=0))
    await manager.async_check(0)
    assert client.read_clock.await_count == 2 and client.set_clock.await_count == 1
    restarted = ClockMaintenance(hass, entry(), client, lambda: now[0])
    await restarted.async_check(0)
    assert client.set_clock.await_count == 1  # Restart reads, but never refreshes every startup.
    now[0] += timedelta(days=1)
    client.read_clock.return_value = encode_clock(now[0].replace(minute=0))
    await restarted.async_check(0)
    assert client.set_clock.await_count == 2
    assert restarted.state["last_reason"] == "daily_refresh_partial_readback"


async def test_failed_correction_is_throttled_across_restart(setup_clock):
    hass, client, manager, now = setup_clock
    client.set_clock.side_effect = TimeoutError
    await manager.async_check(0)
    assert manager.state["status"] == "check_failed"
    restarted = ClockMaintenance(hass, entry(), client, lambda: now[0])
    await restarted.async_check(0)
    assert client.set_clock.await_count == 1 and restarted.state["status"] == "correction_deferred"
    now[0] += timedelta(minutes=59)
    await restarted.async_check(0, force=True)
    assert client.set_clock.await_count == 1
    now[0] += timedelta(minutes=1)
    await restarted.async_check(0, force=True)
    assert client.set_clock.await_count == 2


async def test_timezone_change_is_checked_on_next_poll(setup_clock):
    hass, client, manager, now = setup_clock
    await manager.async_check(0)
    now[0] += timedelta(minutes=10)
    hass.config.time_zone = "America/Chicago"
    now[0] = now[0].astimezone(ZoneInfo("America/Chicago"))
    await manager.async_check(0)
    assert client.set_clock.await_count == 2
    assert manager.state["last_reason"] == "timezone_or_dst_changed"
    assert manager.state["sync_context"]["time_zone"] == "America/Chicago"


async def test_correct_full_readback_needs_no_write_and_manual_sync_is_remembered(setup_clock):
    _, client, manager, now = setup_clock
    client.read_clock.return_value = encode_clock(now[0])
    await manager.async_check(0)
    client.set_clock.assert_not_awaited()
    await client.set_clock(lambda: now[0])
    await manager.async_record_operation(client.clock_operation, reason="manual")
    now[0] += timedelta(minutes=15)
    client.read_clock.return_value = encode_clock(now[0].replace(minute=0))
    await manager.async_check(0, force=True)
    assert client.set_clock.await_count == 1


async def test_missing_read_and_unpersisted_retry_limit_never_write(setup_clock):
    _, client, manager, _ = setup_clock
    client.read_clock.side_effect = ProtocolError("Read rejected")
    await manager.async_check(0)
    client.set_clock.assert_not_awaited()
    client.read_clock.side_effect = None
    with patch.object(manager.store, "async_save", AsyncMock()):
        await manager.async_check(0, force=True)
    client.set_clock.assert_not_awaited()
    assert manager.state["status"] == "check_failed"


async def test_storage_failure_does_not_escape_clock_maintenance(setup_clock):
    _, client, manager, _ = setup_clock
    with patch.object(manager.store, "async_save", AsyncMock(side_effect=OSError("disk unavailable"))):
        await manager.async_check(0)
    client.set_clock.assert_not_awaited()
    assert "save" in manager.state["error"]


async def test_cancelled_automatic_write_keeps_durable_cooldown(setup_clock):
    hass, client, manager, now = setup_clock
    sent = asyncio.Event()

    async def pause(_):
        sent.set()
        await asyncio.Event().wait()

    client.set_clock.side_effect = pause
    task = asyncio.create_task(manager.async_check(0))
    await asyncio.wait_for(sent.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    restarted = ClockMaintenance(hass, entry(), client, lambda: now[0])
    await restarted.async_check(0)
    assert client.set_clock.await_count == 1
    assert restarted.state["status"] == "correction_deferred"


async def test_automatic_correction_uses_real_clock_protocol(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    client, peripheral = make_pair()
    try:
        manager = ClockMaintenance(hass, entry(), client, lambda: LOCAL)
        await manager.async_check(0)
        assert await client.read_clock() == encode_clock(LOCAL)
        assert len(writes(peripheral)) == 1
        assert manager.state["last_operation"]["outcome"] == "readback_confirmed"
        assert manager.state["last_operation"]["rtc_running_verified"] is False
        await manager.async_check(0, force=True)
        assert len(writes(peripheral)) == 1
    finally:
        await client.disconnect()
        await hass.async_stop()


async def test_coordinator_keeps_readings_and_checks_after_recovery_but_not_during_tariff(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    state = HeaterState(125, 4, 5, 0)
    client = SimpleNamespace(
        optional_registers={},
        read_state=AsyncMock(return_value=state),
        read_clock=AsyncMock(side_effect=TimeoutError),
    )
    with patch("custom_components.aosmith_ble.coordinator.make_client", return_value=client):
        coordinator = HeaterCoordinator(hass, entry())
        assert await coordinator._async_update_data() == state
        assert coordinator.clock.state["status"] == "check_failed"
        coordinator.clock.async_check = AsyncMock()
        coordinator.tariff_busy = True
        await coordinator._async_update_data()
        coordinator.clock.async_check.assert_not_awaited()
        coordinator.tariff_busy = False
        client.read_state.side_effect = TimeoutError
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
        client.read_state.side_effect = None
        await coordinator._async_update_data()
        coordinator.clock.async_check.assert_awaited_once_with(0, force=True)
    await hass.async_stop()


async def test_clock_migration_hides_manual_button_once_preserving_inspection(tmp_path):
    from homeassistant.helpers import entity_registry as er

    from custom_components.aosmith_ble import async_migrate_entry
    from custom_components.aosmith_ble.const import DOMAIN

    hass = HomeAssistant(str(tmp_path))
    test_entry = SimpleNamespace(entry_id="clock_test", version=1, minor_version=3, options={})
    registry = MagicMock()
    entities = [
        SimpleNamespace(
            platform=DOMAIN,
            domain="button",
            unique_id="address_" + name,
            entity_id="button." + name,
            disabled_by=None,
        )
        for name in ("set_clock", "inspect", "inspect_schedule")
    ]
    config_entries = SimpleNamespace(async_update_entry=MagicMock())
    with (
        patch.object(er, "async_get", return_value=registry),
        patch.object(er, "async_entries_for_config_entry", return_value=entities),
        patch.object(hass, "config_entries", config_entries),
    ):
        await async_migrate_entry(hass, test_entry)
        registry.async_update_entity.assert_called_once_with(
            "button.set_clock", disabled_by=er.RegistryEntryDisabler.INTEGRATION
        )
        test_entry.minor_version = 4
        registry.reset_mock()
        await async_migrate_entry(hass, test_entry)
        registry.async_update_entity.assert_not_called()
    await hass.async_stop()


async def test_clock_history_storage_error_does_not_lose_tariff_confirmation(tmp_path):
    from test_tariff_clock import PLAN

    hass = HomeAssistant(str(tmp_path))
    client, _ = make_pair()
    try:
        with patch("custom_components.aosmith_ble.coordinator.make_client", return_value=client):
            coordinator = HeaterCoordinator(hass, entry())
            coordinator.async_request_refresh = AsyncMock()
            with patch.object(coordinator.clock.store, "async_save", AsyncMock(side_effect=OSError("disk"))):
                result = await coordinator.async_apply_tariff(PLAN, "More Savings")
            assert result["outcome"] == "readback_confirmed"
            saved = await coordinator.tariff_store.async_load()
            assert saved["last_operation"]["outcome"] == "readback_confirmed"
            assert saved["applied_preference"] == "More Savings"
    finally:
        await client.disconnect()
        await hass.async_stop()


@pytest.mark.parametrize(
    "local,zone,expected",
    [
        ("2026-10-05T21:01:59-04:00", "America/New_York", "2026-10-05T21:02:00-04:00"),
        ("2026-10-05T21:02:00-04:00", "America/New_York", "2026-10-05T22:02:00-04:00"),
        ("2026-10-05T21:49:04-04:00", "America/New_York", "2026-10-05T22:02:00-04:00"),
        ("2026-12-31T23:59:30-05:00", "America/New_York", "2027-01-01T00:02:00-05:00"),
        ("2026-03-08T01:35:00-05:00", "America/New_York", "2026-03-08T03:02:00-04:00"),
        ("2026-11-01T01:35:00-04:00", "America/New_York", "2026-11-01T01:02:00-05:00"),
        ("2026-11-01T01:35:00-05:00", "America/New_York", "2026-11-01T02:02:00-05:00"),
        ("2026-10-04T01:35:00+10:30", "Australia/Lord_Howe", "2026-10-04T03:02:00+11:00"),
    ],
)
def test_hourly_deadline_uses_local_minute_two_across_dst(local, zone, expected):
    now = datetime.fromisoformat(local).astimezone(ZoneInfo(zone))
    target = next_hour_check(now)
    assert target.isoformat() == expected
    assert target.timestamp() > now.timestamp()


async def test_delayed_hourly_check_runs_once_and_realigns(setup_clock):
    _, client, manager, now = setup_clock
    client.read_clock.return_value = encode_clock(now[0])
    await manager.async_check(0)
    now[0] = LOCAL.replace(hour=23, minute=7)
    client.read_clock.return_value = encode_clock(now[0])
    await manager.async_check(0)
    assert client.read_clock.await_count == 2
    assert manager.state["next_check_at"] == "2026-10-06T00:02:00-04:00"
    await manager.async_check(0)
    assert client.read_clock.await_count == 2
    client.set_clock.assert_not_awaited()


async def test_backwards_host_clock_change_does_not_wait_for_stale_deadline(setup_clock):
    _, client, manager, now = setup_clock
    client.read_clock.return_value = encode_clock(now[0])
    await manager.async_check(0)
    now[0] -= timedelta(hours=1)
    client.read_clock.return_value = encode_clock(now[0])
    await manager.async_check(0)
    assert client.read_clock.await_count == 2
    assert manager.state["next_check_at"] == "2026-10-05T21:02:00-04:00"
    await manager.async_check(0)
    assert client.read_clock.await_count == 2
