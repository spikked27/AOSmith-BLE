"""Interpret confirmed tariff bytes using HA local time, never the clock readback."""

import calendar
import hashlib
import json
from datetime import date, datetime, time, timedelta

from .schedule import decode_season, validate_payloads

DR_NAMES = {0: "Baseline", 6: "DR1", 7: "DR2", 8: "DR3", 9: "Load up"}


def decode_dr(word):
    """Observed upper-byte event code; unfamiliar mode data remains unknown."""
    if type(word) is not int or word & 0xFF or word >> 8 not in DR_NAMES:
        return None
    return word >> 8


def schedule_digest(schedule):
    validate_payloads(schedule)
    content = {
        "seasons": [(row["block"], row["value"].upper()) for row in schedule["seasons"]],
        "extra": schedule["extra"]["words"],
    }
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def holiday_dates(words, year):
    """Dates on which clock verification pauses; firmware holiday behavior is unverified."""
    result = set()
    for word in words[:25]:
        if not word:
            continue
        month, day = word >> 12, (word >> 7) & 31
        observed, ordinal, weekday = bool(word & 64), (word >> 3) & 7, word & 7
        if day:
            target = date(year, month, day)
        else:
            if not 1 <= weekday <= 7 or not 1 <= ordinal <= 6:
                raise ValueError("Unsupported holiday rule")
            python_weekday = (weekday + 5) % 7  # App: Sunday=1, Monday=2.
            first = date(year, month, 1)
            target = first + timedelta(days=(python_weekday - first.weekday()) % 7)
            if ordinal == 5:  # Last weekday of month.
                last = date(year, month, calendar.monthrange(year, month)[1])
                target = last - timedelta(days=(last.weekday() - python_weekday) % 7)
            elif ordinal == 6:  # Election day: Tuesday after first Monday.
                if weekday != 3:
                    raise ValueError("Unsupported holiday ordinal")
                target = first + timedelta(days=(0 - first.weekday()) % 7 + 1)
            else:
                target += timedelta(weeks=ordinal - 1)
        result.add(target)
        if observed and target.weekday() in (5, 6):
            result.add(target + timedelta(days=-1 if target.weekday() == 5 else 1))
    return result


def tariff_timing(schedule, now):
    """Return current level and actual value-changing boundaries, or a pause reason.

    Conservative exclusions prevent holiday, seasonal and DST ambiguity from
    becoming a clock write. Includes prior-day carry and year-wrapping seasons.
    """
    if now.tzinfo is None:
        raise ValueError("Local time must include a timezone")
    validate_payloads(schedule)
    seasons = [decode_season(row["value"]) for row in schedule["seasons"] if int(row["value"], 16)]
    if not seasons:
        return {"reason": "No tariff events"}
    for season in seasons:
        date(2000, season["start_month"], season["start_day"])
        if season["second_month"] or season["second_day"]:
            return {"reason": "Unsupported season header"}
        for event in season["events"]:
            if (
                event["mode"] not in DR_NAMES
                or event["mode_data"]
                or event["unused"]
                or not 0 < event["days_of_week"] < 128
            ):
                return {"reason": "Unsupported tariff event"}
            time(event["hour"], event["minute"])
    seasons.sort(key=lambda s: (s["start_month"], s["start_day"]))
    if len({(s["start_month"], s["start_day"]) for s in seasons}) != len(seasons):
        return {"reason": "Ambiguous season headers"}
    today = now.date()
    holidays = set()
    for year in (today.year - 1, today.year, today.year + 1):
        holidays |= holiday_dates(schedule["extra"]["words"], year)
    if today in holidays or today - timedelta(days=1) in holidays:
        return {"reason": "Holiday schedule verification paused"}
    midnight = datetime.combine(today, time(), now.tzinfo)
    if midnight.utcoffset() != (midnight + timedelta(days=1)).utcoffset():
        return {"reason": "DST transition day verification paused"}
    if (today.month, today.day) in {(s["start_month"], s["start_day"]) for s in seasons}:
        return {"reason": "Season change verification paused"}
    events = []
    for offset in range(-8, 9):
        day = today + timedelta(days=offset)
        eligible = [s for s in seasons if (s["start_month"], s["start_day"]) <= (day.month, day.day)]
        season = eligible[-1] if eligible else seasons[-1]
        mask = 1 << ((day.weekday() + 1) % 7)
        seen = set()
        for event in season["events"]:
            if not event["days_of_week"] & mask:
                continue
            at = datetime.combine(day, time(event["hour"], event["minute"]), now.tzinfo)
            if at in seen:
                return {"reason": "Overlapping tariff events"}
            seen.add(at)
            events.append((at, event["mode"]))
    events.sort()
    changes = [
        {"at": after[0], "before": before[1], "after": after[1]}
        for before, after in zip(events, events[1:])
        if before[1] != after[1]
    ]
    current = [event for event in events if event[0] <= now]
    previous = [change for change in changes if change["at"] <= now]
    upcoming = [change for change in changes if change["at"] > now]
    if not current or not previous or not upcoming:
        return {"reason": "No distinct tariff transition available"}
    return {"expected": current[-1][1], "transition": previous[-1], "next": upcoming[0], "reason": None}
