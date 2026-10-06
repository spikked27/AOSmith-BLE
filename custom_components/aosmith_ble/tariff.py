"""Anonymous AO Smith tariff lookup and cached normalized rate-plan data."""

import asyncio
import math
import re
from datetime import date, datetime, timezone

import aiohttp

ENDPOINT = "https://r2.wh8.co/graphql"
HEADERS = {"brand": "icomm", "version": "14.1.0"}
UTILITIES_QUERY = """query getUtilitiesForZipcode($zipcode: String!) {
  utilitiesForZipcode(zipcode: $zipcode) { name lseId }
}"""
TARIFFS_QUERY = """query tariffsForUtility($utilityID: ID!) {
  tariffsForUtility(lseId: $utilityID) { masterTariffId tariffCode tariffName }
}"""
PLAN_QUERY = """query timeOfUseData($tariffID: ID!) {
  tariffAndHoliday(masterTariffId: $tariffID) {
    holidays { calendarEventId calendarEventName }
    touEvents { day fromDayOfWeek hour minute mode modeData month rate toDayOfWeek }
  }
}"""


class TariffError(Exception):
    """Lookup failed or the service returned an unsupported plan."""


class TariffLookup:
    def __init__(self, session):
        self.session = session

    async def _query(self, query, variables, key):
        try:
            async with asyncio.timeout(20):
                async with self.session.post(
                    ENDPOINT,
                    json={"query": query, "variables": variables},
                    headers=HEADERS,
                    allow_redirects=False,
                ) as response:
                    if response.status != 200:
                        raise TariffError("Tariff service unavailable")
                    payload = await response.json()
            if not isinstance(payload, dict) or payload.get("errors"):
                raise TariffError("Tariff service rejected the lookup")
            data = payload.get("data")
            if not isinstance(data, dict) or key not in data or data[key] is None:
                raise TariffError("Tariff response is incomplete")
            return data[key]
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise TariffError("Could not retrieve tariff data") from err

    async def utilities(self, zipcode):
        if not re.fullmatch(r"[0-9]{5}", zipcode):
            raise TariffError("Enter a five-digit US ZIP code")
        rows = await self._query(UTILITIES_QUERY, {"zipcode": zipcode}, "utilitiesForZipcode")
        return _choices(rows, "lseId", ("name",))

    async def tariffs(self, utility_id):
        rows = await self._query(TARIFFS_QUERY, {"utilityID": utility_id}, "tariffsForUtility")
        return _choices(rows, "masterTariffId", ("tariffCode", "tariffName"))

    async def plan(self, tariff_id):
        return validate_plan(await self._query(PLAN_QUERY, {"tariffID": tariff_id}, "tariffAndHoliday"))


def _choices(rows, id_key, label_keys):
    if not isinstance(rows, list):
        raise TariffError("Invalid tariff list")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or row.get(id_key) is None:
            raise TariffError("Incomplete tariff list")
        if any(not isinstance(row.get(key), str) or not row[key].strip() for key in label_keys):
            raise TariffError("Missing tariff label")
        result[str(row[id_key])] = " — ".join(row[key] for key in label_keys)
    if not result:
        raise TariffError("No matching tariffs or utilities")
    return result


def validate_plan(data):
    """Preserve all seasonal and holiday data, including unknown holiday IDs."""
    if not isinstance(data, dict):
        raise TariffError("Invalid tariff plan")
    events, holidays = data.get("touEvents"), data.get("holidays")
    if not isinstance(events, list) or not events or not isinstance(holidays, list):
        raise TariffError("Missing tariff events or holidays")
    if len(events) > 100 or len(holidays) > 25:
        raise TariffError("Tariff exceeds the heater's 100 event / 25 holiday capacity")
    cleaned = []
    fields = ("month", "day", "fromDayOfWeek", "toDayOfWeek", "hour", "minute", "rate", "mode", "modeData")
    for event in events:
        if not isinstance(event, dict):
            raise TariffError("Invalid tariff event")
        for key, minimum, maximum in (
            ("month", 1, 12),
            ("day", 1, 31),
            ("hour", 0, 23),
            ("minute", 0, 59),
            ("fromDayOfWeek", 0, 6),
            ("toDayOfWeek", 0, 6),
            ("mode", 0, 255),
            ("modeData", 0, 255),
        ):
            if type(event.get(key)) is not int or not minimum <= event[key] <= maximum:
                raise TariffError("Invalid tariff event field")
        try:
            date(2000, event["month"], event["day"])
        except ValueError as err:
            raise TariffError("Invalid tariff season date") from err
        if event["fromDayOfWeek"] > event["toDayOfWeek"]:
            raise TariffError("Unsupported weekday range")
        rate = event.get("rate")
        if type(rate) not in (int, float) or not math.isfinite(rate):
            raise TariffError("Invalid tariff price")
        cleaned.append({key: event[key] for key in fields})
    for holiday in holidays:
        if (
            not isinstance(holiday, dict)
            or type(holiday.get("calendarEventId")) is not int
            or not isinstance(holiday.get("calendarEventName"), str)
        ):
            raise TariffError("Invalid tariff holiday")
    return {
        "touEvents": cleaned,
        "holidays": [
            {"calendarEventId": h["calendarEventId"], "calendarEventName": h["calendarEventName"]}
            for h in holidays
        ],
    }


def cache_plan(plan, utility_id, utility_name, tariff_id, tariff_name):
    return {
        "schema_version": 1,
        "source": "AO Smith tariff lookup",
        "utility_id": utility_id,
        "utility_name": utility_name,
        "tariff_id": tariff_id,
        "tariff_name": tariff_name,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        **validate_plan(plan),
    }
