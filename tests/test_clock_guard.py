"""Observed DR replay and failure cases for transition-driven clock correction."""

import asyncio
import json
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.core import HomeAssistant
from test_tariff_clock import entry, make_pair, writes

from custom_components.aosmith_ble.client import HeaterState
from custom_components.aosmith_ble.clock_guard import ClockGuard
from custom_components.aosmith_ble.const import CONF_AUTO_CLOCK
from custom_components.aosmith_ble.coordinator import HeaterCoordinator
from custom_components.aosmith_ble.protocol import ProtocolError
from custom_components.aosmith_ble.timing import decode_dr, holiday_dates, schedule_digest, tariff_timing

FIXTURE = json.loads((Path(__file__).parent / "fixtures/dr_transition_20261007.json").read_text())
ZONE = ZoneInfo("America/New_York")
BOUNDARY = datetime(2026, 10, 7, 22, tzinfo=ZONE)


def state(at, code=6, **updates):
    registers = {
        "dr_status": code << 8,
        "energy_preference_experimental": 0,
        "utility_override": 0,
        "utility_enrollment": 0,
        "cta_present": 0,
        "advanced_load": 0,
    }
    registers.update(updates.pop("registers", {}))
    return HeaterState(
        **{"target_temperature": 125, "mode": 4, "availability": 0, "fault": 0, **updates},
        registers=registers,
        register_read_at={"dr_status": at.isoformat()},
    )


@pytest.fixture
async def harness(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    hass.config.time_zone = "America/New_York"
    schedule = deepcopy(FIXTURE["schedule"])
    client = SimpleNamespace(
        optional_registers={},
        clock_operation=None,
        inspect_schedule=AsyncMock(return_value={**schedule, "complete": True}),
        read_state=AsyncMock(),
        set_clock=AsyncMock(),
    )
    with patch("custom_components.aosmith_ble.coordinator.make_client", return_value=client):
        coordinator = HeaterCoordinator(hass, entry())
    coordinator.tariff_state = {
        "applied_schedule": schedule,
        "applied_plan": {"saved": True},
        "applied_at": "2026-10-05T22:23:33-04:00",
        "applied_preference": "More Savings",
        "last_operation": {"outcome": "readback_confirmed"},
    }
    h = SimpleNamespace(hass=hass, coordinator=coordinator, client=client, now=BOUNDARY)
    coordinator.local_now = lambda: h.now
    coordinator.clock.local_now = coordinator.local_now

    async def clock_write(local_now):
        client.clock_operation = {
            "time": local_now().isoformat(),
            "outcome": "acknowledged",
            "requested_words": [22, 13639],
        }
        return client.clock_operation

    client.set_clock.side_effect = clock_write

    async def observe(seconds, code=6, **updates):
        h.now = BOUNDARY + timedelta(seconds=seconds)
        fresh = state(h.now, code, **updates)
        client.read_state.return_value = fresh
        await coordinator.clock_guard.async_observe(fresh)

    h.observe = observe
    yield h
    await hass.async_stop()


async def miss(h, boundary_offset=0, **updates):
    for seconds in range(-90, 241, 30):
        await h.observe(boundary_offset + seconds, **updates)


def test_tariff_day_masks_seasons_and_overnight_carry():
    schedule = FIXTURE["schedule"]
    for day, hour, expected in [
        (7, 2, 0),
        (7, 4, 9),
        (7, 7, 6),
        (7, 16, 7),
        (7, 20, 6),
        (7, 23, 0),
        (10, 16, 6),
        (11, 1, 0),
    ]:
        result = tariff_timing(schedule, datetime(2026, 10, day, hour, tzinfo=ZONE))
        assert result["expected"] == expected
    assert tariff_timing(schedule, datetime(2027, 1, 7, 16, tzinfo=ZONE))["expected"] == 7
    assert tariff_timing(schedule, datetime(2026, 7, 8, 16, tzinfo=ZONE))["expected"] == 7


def test_only_value_changes_are_boundaries():
    schedule = deepcopy(FIXTURE["schedule"])
    # October weekday 15:00 and 19:00 both become DR1.
    row = schedule["seasons"][1]
    payload = bytearray.fromhex(row["value"])
    for i in range(4, 124, 6):
        if payload[i] == 15 and payload[i + 3] == 62:
            payload[i + 4] = 6
    row["value"] = payload.hex()
    timing = tariff_timing(schedule, BOUNDARY.replace(hour=16))
    assert timing["transition"]["at"].hour == 6
    assert timing["next"]["at"].hour == 22


@pytest.mark.parametrize(
    "at,reason",
    [
        (datetime(2026, 11, 1, 12, tzinfo=ZONE), "DST"),
        (datetime(2026, 10, 1, 12, tzinfo=ZONE), "Season"),
        (datetime(2026, 12, 25, 12, tzinfo=ZONE), "Holiday"),
        (datetime(2026, 12, 26, 12, tzinfo=ZONE), "Holiday"),
    ],
)
def test_ambiguous_calendar_days_pause(at, reason):
    assert reason in tariff_timing(FIXTURE["schedule"], at)["reason"]


def test_holiday_rules_include_observed_last_weekday_and_election():
    assert {date(2021, 7, 4), date(2021, 7, 5)} <= holiday_dates([0x7240], 2021)
    assert date(2026, 5, 25) in holiday_dates([(5 << 12) | (5 << 3) | 2], 2026)
    assert date(2026, 11, 3) in holiday_dates([(11 << 12) | (6 << 3) | 3], 2026)


@pytest.mark.parametrize(
    "word,expected",
    [(0, 0), (1536, 6), (1792, 7), (2048, 8), (2304, 9), (7, None), (65535, None), (None, None)],
)
def test_dr_uses_upper_byte_and_rejects_unrecognized_data(word, expected):
    assert decode_dr(word) == expected


async def test_real_owner_transition_replay_never_sets_clock(harness):
    h = harness
    for sample in FIXTURE["samples"]:
        at = datetime.fromisoformat(sample["read_at"]).astimezone(ZONE)
        await h.observe((at - BOUNDARY).total_seconds(), sample["raw"] >> 8)
    data = h.coordinator.clock_guard.data
    assert data["status"] == "In sync"
    assert data["last_verified_transition"] == BOUNDARY.isoformat()
    assert data["desync_count"] == 0
    h.client.set_clock.assert_not_awaited()
    h.client.inspect_schedule.assert_not_awaited()


async def test_miss_writes_once_and_preserves_desync_until_later_transition(harness):
    h = harness
    await miss(h)
    guard = h.coordinator.clock_guard
    assert guard.data["desync_active"] and guard.data["desync_count"] == 1
    assert guard.data["status"] == "Clock set; awaiting verification"
    assert guard.data["last_correction_outcome"] == "acknowledged"
    h.client.set_clock.assert_awaited_once()
    assert h.coordinator.clock.state["last_reason"] == "missed_tariff_transition"
    for seconds in range(270, 901, 30):
        await h.observe(seconds, 0)
    assert guard.data["desync_active"]  # Seeing baseline later cannot establish correct timing.
    # Next event is 03:00 load up; an on-time observation resolves the active problem.
    for seconds in range(17910, 18061, 30):
        await h.observe(seconds, 0 if seconds < 18000 else 9)
    assert guard.data["status"] == "In sync" and not guard.data["desync_active"]
    assert guard.data["desync_count"] == 1 and guard.data["last_desync_at"]
    saved = await guard.store.async_load()
    assert saved["last_auto_attempt_at"] and saved["resolved_at"]
    h.client.set_clock.assert_awaited_once()


async def test_disabled_policy_detects_without_writing(harness):
    h = harness
    h.coordinator.options[CONF_AUTO_CLOCK] = False
    await miss(h)
    assert h.coordinator.clock_guard.data["status"] == "Clock desync detected"
    h.client.set_clock.assert_not_awaited()
    h.client.inspect_schedule.assert_not_awaited()


@pytest.mark.parametrize(
    "updates",
    [
        {"mode": 1},
        {"mode": 2},
        {"mode": 3},
        {"mode": 5},
        {"fault": 13},
        {"registers": {"utility_override": 1}},
        {"registers": {"cta_present": 1}},
        {"registers": {"advanced_load": 165}},
        {"registers": {"utility_enrollment": 1}},
        {"registers": {"energy_preference_experimental": 1}},
        {"registers": {"dr_status": 65535}},
    ],
)
async def test_ineligible_state_never_claims_desync(harness, updates):
    await miss(harness, **updates)
    assert not harness.coordinator.clock_guard.data["desync_active"]
    harness.client.set_clock.assert_not_awaited()


@pytest.mark.parametrize("scenario", ["offline", "mode_change", "setpoint_change", "no_before", "backwards"])
async def test_incomplete_observation_cannot_trigger_correction(harness, scenario):
    h = harness
    await h.observe(-90)
    await h.observe(-60)
    if scenario == "offline":
        h.coordinator.clock_guard.unavailable()
    elif scenario == "no_before":
        h.coordinator.clock_guard.samples.clear()
    elif scenario == "backwards":
        await h.observe(-120)
        h.coordinator.clock_guard.unavailable()
    for seconds in range(30, 301, 30):
        await h.observe(
            seconds,
            **(
                {"mode": 1}
                if scenario == "mode_change"
                else {"target_temperature": 130}
                if scenario == "setpoint_change"
                else {}
            ),
        )
    h.client.set_clock.assert_not_awaited()
    assert not h.coordinator.clock_guard.data["desync_active"]


async def test_repeated_or_stale_timestamp_is_not_fresh_evidence(harness):
    h = harness
    await h.observe(-90)
    await h.observe(-60)
    h.now = BOUNDARY + timedelta(minutes=5)
    old = state(BOUNDARY - timedelta(minutes=1))
    for _ in range(10):
        await h.coordinator.clock_guard.async_observe(old)
    assert h.coordinator.clock_guard.data["status"] == "Check unavailable"
    h.client.set_clock.assert_not_awaited()


@pytest.mark.parametrize("capture", ["incomplete", "different", "read_error"])
async def test_actual_schedule_must_match_before_any_clock_write(harness, capture):
    h = harness
    if capture == "incomplete":
        h.client.inspect_schedule.return_value = {"complete": False}
    elif capture == "different":
        h.client.inspect_schedule.return_value["extra"]["words"][26] ^= 1
        # Ensure the expected bytes themselves weren't modified through shared lists.
        h.coordinator.tariff_state["applied_schedule"] = deepcopy(FIXTURE["schedule"])
    else:
        h.client.inspect_schedule.side_effect = TimeoutError
    await miss(h)
    assert h.coordinator.clock_guard.data["desync_active"]
    assert h.coordinator.clock_guard.data["status"] in ("Schedule mismatch", "Correction failed")
    h.client.set_clock.assert_not_awaited()


@pytest.mark.parametrize("change", ["late_transition", "override", "time_zone", "deadline"])
async def test_conditions_rechecked_after_slow_schedule_read(harness, change):
    h = harness

    async def capture():
        if change == "time_zone":
            h.now = h.now.astimezone(ZoneInfo("UTC"))
        if change == "deadline":
            h.now += timedelta(minutes=15)
        h.client.read_state.return_value = state(
            h.now,
            0 if change == "late_transition" else 6,
            registers={"utility_override": int(change == "override")},
        )
        return {**deepcopy(FIXTURE["schedule"]), "complete": True}

    h.client.inspect_schedule.side_effect = capture
    await miss(h)
    h.client.set_clock.assert_not_awaited()


@pytest.mark.parametrize("failed", [False, True])
async def test_restart_does_not_allow_repeat_of_attempted_correction(harness, failed):
    h = harness
    if failed:
        h.client.set_clock.side_effect = ProtocolError("No clock acknowledgement")
    await miss(h)
    h.coordinator.clock_guard = ClockGuard(h.hass, h.coordinator)
    # Next morning at 06:00 should move from load up to DR1; simulate another miss.
    await miss(h, 8 * 3600, code=9)
    assert h.coordinator.clock_guard.data["status"] == "Manual attention required"
    assert h.coordinator.clock_guard.data["desync_count"] == 1
    h.client.set_clock.assert_awaited_once()


async def test_durable_limit_must_be_confirmed_before_clock_write(harness):
    with patch("custom_components.aosmith_ble.clock_guard._saved_attempt", return_value=(None, False)):
        await miss(harness)
    assert harness.coordinator.clock_guard.data["status"] == "Correction failed"
    harness.client.set_clock.assert_not_awaited()


async def test_cancellation_keeps_attempt_limit_and_releases_coordinator_lock(harness):
    h = harness
    h.client.set_clock.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        async with h.coordinator.command_lock:
            await miss(h)
    assert not h.coordinator.command_lock.locked()
    assert (await h.coordinator.clock_guard.store.async_load())["correction_attempted"]


async def test_one_actual_wire_clock_write_after_a_missed_transition(harness):
    h = harness
    client, peripheral = make_pair()
    h.client.set_clock.side_effect = client.set_clock
    try:
        await miss(h)
        assert len([p for p in writes(peripheral) if p[3] == 26]) == 1
        assert h.coordinator.clock_guard.data["status"] == "Clock set; awaiting verification"
    finally:
        await client.disconnect()


def test_schedule_digest_ignores_capture_metadata_and_hex_case():
    other = deepcopy(FIXTURE["schedule"])
    other["complete"] = True
    for row in other["seasons"]:
        row["value"] = row["value"].lower()
    assert schedule_digest(other) == schedule_digest(FIXTURE["schedule"])


async def test_new_episode_inside_24_hours_still_cannot_write_again(harness):
    h = harness
    await miss(h)
    for seconds in range(17910, 18061, 30):
        await h.observe(seconds, 0 if seconds < 18000 else 9)
    await miss(h, 8 * 3600, code=9)
    assert h.coordinator.clock_guard.data["desync_count"] == 2
    assert "24 hours" in h.coordinator.clock_guard.data["reason"]
    h.client.set_clock.assert_awaited_once()


async def test_missing_fresh_override_status_pauses_verification(harness):
    h = harness
    for seconds in range(-90, 241, 30):
        h.now = BOUNDARY + timedelta(seconds=seconds)
        reading = state(h.now)
        del reading.registers["utility_override"]
        await h.coordinator.clock_guard.async_observe(reading)
    assert h.coordinator.clock_guard.data["reason"] == "Utility status unavailable"
    assert not h.coordinator.clock_guard.data["desync_active"]
    h.client.set_clock.assert_not_awaited()


async def test_old_applied_plan_is_rebuilt_instead_of_using_unconfirmed_candidate(harness):
    from test_tariff_clock import PLAN

    from custom_components.aosmith_ble.schedule import build_schedule

    h = harness
    tariff = h.coordinator.tariff_state
    del tariff["applied_schedule"]
    tariff["applied_plan"] = PLAN
    tariff["generated_schedule"] = {"unconfirmed": True}
    assert await h.coordinator.clock_guard._schedule() == build_schedule(PLAN, "More Savings")
    tariff["last_operation"]["outcome"] = "partial_or_unconfirmed"
    assert await h.coordinator.clock_guard._schedule() is None


async def test_corrupt_tariff_disables_guard_without_losing_core_readings(harness):
    h = harness
    h.coordinator.tariff_state["applied_schedule"]["extra"]["words"] = []
    reading = state(BOUNDARY)
    h.client.read_state.return_value = reading
    assert await h.coordinator._async_update_data() == reading
    assert h.coordinator.clock_guard.data["status"] == "Check unavailable"
    h.client.set_clock.assert_not_awaited()


async def test_corrupt_legacy_plan_does_not_interrupt_core_readings(harness):
    h = harness
    del h.coordinator.tariff_state["applied_schedule"]
    h.coordinator.tariff_state["applied_plan"] = {"invalid": "older saved plan"}
    reading = state(BOUNDARY)
    h.client.read_state.return_value = reading
    assert await h.coordinator._async_update_data() == reading
    assert h.coordinator.clock_guard.data["status"] == "Check unavailable"
    h.client.set_clock.assert_not_awaited()
