"""Tariff setup/cache isolation, untrusted responses and offline behavior."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.aosmith_ble.config_flow import OptionsFlow
from custom_components.aosmith_ble.sensor import TariffSensor
from custom_components.aosmith_ble.tariff import TariffError, TariffLookup, cache_plan, validate_plan

PLAN = {
    "holidays": [{"calendarEventId": 999, "calendarEventName": "Preserved unknown holiday"}],
    "touEvents": [
        {
            "month": 6,
            "day": 1,
            "hour": 22,
            "minute": 0,
            "fromDayOfWeek": 0,
            "toDayOfWeek": 6,
            "mode": 0,
            "modeData": 0,
            "rate": 0.12,
        },
        {
            "month": 10,
            "day": 1,
            "hour": 15,
            "minute": 0,
            "fromDayOfWeek": 0,
            "toDayOfWeek": 4,
            "mode": 0,
            "modeData": 0,
            "rate": 0.52,
        },
    ],
}


def test_cache_preserves_seasons_weekdays_and_unknown_holidays():
    cache = cache_plan(PLAN, "200", "Example utility", "3439409", "195 — Residential")
    assert cache["touEvents"] == PLAN["touEvents"]
    assert cache["holidays"] == PLAN["holidays"]
    assert "zipcode" not in cache and "token" not in cache
    PLAN_COPY = deepcopy(PLAN)
    cache["touEvents"][0]["rate"] = 1
    assert PLAN == PLAN_COPY


@pytest.mark.parametrize(
    "field,value",
    [
        ("hour", 24),
        ("minute", -1),
        ("month", 13),
        ("fromDayOfWeek", True),
        ("rate", float("nan")),
        ("rate", float("inf")),
        ("rate", "0.10"),
    ],
)
def test_invalid_tariff_cannot_be_saved(field, value):
    bad = deepcopy(PLAN)
    bad["touEvents"][0][field] = value
    with pytest.raises(TariffError):
        validate_plan(bad)


async def test_lookup_has_no_login_and_rejects_graphql_errors():
    response = MagicMock(status=200)
    response.json = AsyncMock(
        return_value={
            "data": {
                "utilitiesForZipcode": [
                    {"lseId": 200, "name": "Example utility"},
                ]
            }
        }
    )
    manager = MagicMock()
    manager.__aenter__ = AsyncMock(return_value=response)
    manager.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.post.return_value = manager
    lookup = TariffLookup(session)
    assert await lookup.utilities("12345") == {"200": "Example utility"}
    arguments = session.post.call_args.kwargs
    assert not any(key.lower() == "authorization" for key in arguments["headers"])
    assert arguments["allow_redirects"] is False
    assert arguments["json"]["variables"] == {"zipcode": "12345"}
    response.json.return_value = {"errors": [{"message": "server error"}], "data": {}}
    with pytest.raises(TariffError):
        await lookup.utilities("12345")
    response.status = 503
    with pytest.raises(TariffError):
        await lookup.utilities("12345")


async def test_tariff_options_preserve_settings_and_previous_cache_on_failure(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    entry = SimpleNamespace(
        options={
            "poll_interval": 45,
            "enable_setpoint_writes": False,
            "tariff": {"old": "plan"},
            "enable_utility_controls": True,
        }
    )
    flow = OptionsFlow()
    flow.hass = hass
    lookup = SimpleNamespace(
        utilities=AsyncMock(return_value={"200": "Example utility"}),
        tariffs=AsyncMock(return_value={"3439409": "195 — Residential"}),
        plan=AsyncMock(side_effect=TariffError("unavailable")),
    )
    with (
        patch.object(OptionsFlow, "config_entry", new_callable=PropertyMock, return_value=entry),
        patch.object(flow, "_lookup", return_value=lookup),
    ):
        assert (await flow.async_step_init())["type"] == "menu"
        assert (await flow.async_step_tariff({"zipcode": "bad"}))["errors"]["zipcode"] == "invalid_zipcode"
        lookup.utilities.assert_not_awaited()
        assert (await flow.async_step_tariff({"zipcode": "12345"}))["step_id"] == "utility"
        assert (await flow.async_step_utility({"utility_id": "200"}))["step_id"] == "rate"
        failed = await flow.async_step_rate({"tariff_id": "3439409"})
        assert failed["errors"]["base"] == "tariff_lookup_failed"
        assert entry.options["tariff"] == {"old": "plan"}
        lookup.plan.side_effect = None
        lookup.plan.return_value = PLAN
        assert (await flow.async_step_rate({"tariff_id": "3439409"}))["step_id"] == "tariff_confirm"
        result = await flow.async_step_tariff_confirm({})
        assert result["data"]["poll_interval"] == 45
        assert result["data"]["enable_setpoint_writes"] is False
        assert result["data"]["tariff"]["tariff_id"] == "3439409"
        assert "enable_utility_controls" not in result["data"]
        assert "12345" not in str(result["data"])
        settings = await flow.async_step_settings({"poll_interval": 60})
        assert settings["data"]["tariff"] == {"old": "plan"}
        removed = await flow.async_step_remove_tariff({})
        assert removed["data"]["tariff"] is None and removed["data"]["poll_interval"] == 45
    await hass.async_stop()


def test_tariff_preview_works_offline_without_any_heater_writes():
    coordinator = SimpleNamespace(address="AA:BB:CC:DD:EE:FF", last_update_success=False)
    plan = cache_plan(PLAN, "200", "Example utility", "3439409", "195 — Residential")
    entity = TariffSensor(coordinator, SimpleNamespace(options={"tariff": plan}))
    assert entity.available
    assert entity.native_value == "195 — Residential"
    assert entity.extra_state_attributes["schedule"] == PLAN["touEvents"]
    assert "not implemented" in entity.extra_state_attributes["heater_programming"]
