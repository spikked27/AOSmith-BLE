"""App-derived TOU generation and complete season payloads; no I/O."""

import math

from .tariff import validate_plan

PREFERENCES = {"More Hot Water": 1, "More Savings": 2, "Most Savings": 3}
BLE_PREFERENCE_WORDS = {"More Hot Water": 1, "More Savings": 0, "Most Savings": 2}


def event_mode(preference, minimum, maximum, current, low=1.1, high=1.2):
    """Functions 14539–14541; preserve the app's floating-point operation order."""
    if current <= minimum:
        return 0
    ratio = maximum / minimum
    ratio_cap = 1 if ratio < low else 3 if ratio > high else 2
    level_cap = min(max(0, min(preference or 0, 3)), ratio_cap)
    slope = level_cap / (maximum - minimum)
    offset = -1 * slope * minimum
    level = math.floor(slope * current + offset + 0.5)  # JS Math.round, nonnegative inputs
    return level + 5 if level > 0 else 0


def day_mask(first, last):
    """14533/14536: input Monday=0; wire Sunday=bit 0, Monday=bit 1."""
    return sum(1 << ((day + 1) % 7) for day in range(first, last + 1))


def sort_key(event):
    return tuple(event[key] for key in ("month", "day", "daysOfWeek", "hour", "minute"))


def uses_base_price(events, candidate, minimum):
    """14524–14527, including the original component-wise hour/minute checks."""
    same_days = [
        event
        for event in events
        if all(event[key] == candidate[key] for key in ("month", "day", "daysOfWeek"))
    ]
    chosen = None
    for event in same_days:
        if candidate["hour"] >= event["hour"] and candidate["minute"] >= event["minute"]:
            if chosen is None or (event["hour"] >= chosen["hour"] and event["minute"] >= chosen["minute"]):
                chosen = event
    if chosen is None:
        for event in same_days:
            if chosen is None or (event["hour"] >= chosen["hour"] and event["minute"] >= chosen["minute"]):
                chosen = event
    return chosen is not None and chosen["rate"] == minimum


def make_events(rates, preference):
    """14511–14527, for well-formed normalized input with positive weekday rates."""
    limits = {}
    for rate in rates:
        key = (rate["month"], rate["day"])
        bounds = limits.setdefault(key, [10000, 0])
        if rate["fromDayOfWeek"] < 5:
            bounds[0] = min(bounds[0], rate["rate"])
            bounds[1] = max(bounds[1], rate["rate"])
    split = []
    for rate in rates:
        if rate["fromDayOfWeek"] == 0 and rate["toDayOfWeek"] == 6:
            split.extend([{**rate, "toDayOfWeek": 4}, {**rate, "fromDayOfWeek": 5}])
        else:
            split.append(dict(rate))
    events = []
    for rate in split:
        minimum, maximum = limits[(rate["month"], rate["day"])]
        if not 0 < minimum <= maximum:
            raise ValueError("Each season must include a positive weekday price range")
        events.append(
            {
                **{key: rate[key] for key in ("month", "day", "hour", "minute", "rate")},
                "daysOfWeek": day_mask(rate["fromDayOfWeek"], rate["toDayOfWeek"]),
                "mode": event_mode(preference, minimum, maximum, rate["rate"]),
                "modeData": 0,
            }
        )
    events.sort(key=sort_key)
    result = []
    for event in events:
        minimum = limits[(event["month"], event["day"])][0]
        if event["rate"] > minimum:
            # Default load-up lead is three hours. The app wraps the hour while
            # retaining the event's existing weekday mask and season date.
            candidate = {**event, "hour": (event["hour"] - 3) % 24, "mode": 9, "rate": minimum}
            if uses_base_price(events, candidate, minimum):
                result.append(candidate)
        result.append(event)
    return sorted(result, key=sort_key)


def encode_event(event):
    """14530: hour, minute, unused byte, weekday mask, mode, modeData."""
    return bytes((event["hour"], event["minute"], 0, event["daysOfWeek"], event["mode"], 0))


def encode_seasons(events):
    """14531/14543–14545: five blocks, four header bytes and twenty 6-byte slots."""
    grouped = {}
    for event in events:
        grouped.setdefault((event["month"], event["day"]), []).append(event)
    if len(grouped) > 5 or any(len(group) > 20 for group in grouped.values()):
        raise ValueError("Exceeds the app's five seasons / twenty event slots")
    blocks = []
    for (month, day), group in grouped.items():
        payload = bytes((month, day, 0, 0)) + b"".join(map(encode_event, group))
        blocks.append({"block": 21 + len(blocks), "value": payload.ljust(124, b"\0").hex().upper()})
    while len(blocks) < 5:
        blocks.append({"block": 21 + len(blocks), "value": "00" * 124})
    return blocks


# iCOMM module 1413: weekday, ordinal, observed flag, day of month, month.
HOLIDAY_RULES = {
    2: (0, 0, 1, 1, 1),
    20: (2, 3, 0, 0, 1),
    4: (0, 0, 0, 12, 2),
    21: (2, 3, 0, 0, 2),
    6: (0, 0, 0, 18, 2),
    7: (0, 0, 0, 17, 3),
    2726: (0, 0, 0, 1, 5),
    10: (2, 5, 0, 0, 5),
    11: (0, 0, 0, 14, 6),
    12: (0, 0, 1, 4, 7),
    2723: (0, 0, 0, 14, 7),
    2724: (0, 0, 0, 15, 8),
    27: (2, 1, 0, 0, 9),
    30: (2, 2, 0, 0, 10),
    15: (0, 0, 0, 31, 10),
    16: (0, 0, 0, 1, 11),
    33: (3, 6, 0, 0, 11),
    17: (0, 0, 0, 11, 11),
    34: (5, 4, 0, 0, 11),
    18: (0, 0, 1, 25, 12),
}


def build_schedule(plan, preference):
    """Compile the cached API response; use the contiguous 28:50–78 mapping."""
    if preference not in PREFERENCES:
        raise ValueError("Choose a valid energy preference")
    plan = validate_plan(plan)
    if any(not 0 < event["rate"] < 10000 for event in plan["touEvents"]):
        raise ValueError("This schedule generator requires positive tariff prices below 10000")
    events = make_events(plan["touEvents"], PREFERENCES[preference])
    if any(event["mode"] not in (0, 6, 7, 8, 9) for event in events):
        raise ValueError("Tariff prices produced an unsupported demand-response level")
    holidays = []
    for holiday in plan["holidays"]:
        rule = HOLIDAY_RULES.get(holiday["calendarEventId"])
        if rule is None:
            raise ValueError(
                f"Unsupported holiday: {holiday['calendarEventName']} ({holiday['calendarEventId']})"
            )
        weekday, ordinal, observed, day, month = rule
        holidays.append((month << 12) | (day << 7) | (observed << 6) | (ordinal << 3) | weekday)
    if len(holidays) > 25:
        raise ValueError("Tariff exceeds the 25 holiday slots")
    extra = holidays + [0] * (25 - len(holidays))
    extra += [BLE_PREFERENCE_WORDS[preference], 0x011A, 0x0133, 0x0300]
    result = {
        "preference": preference,
        "events": events,
        "seasons": encode_seasons(events),
        "extra": {"block": 28, "parameter": 50, "words": extra},
    }
    validate_payloads(result)
    return result


def validate_payloads(schedule):
    """Allow only the recovered five season blocks and contiguous tariff region."""
    seasons = schedule.get("seasons")
    if not isinstance(seasons, list) or [b.get("block") for b in seasons] != list(range(21, 26)):
        raise ValueError("Expected exactly season blocks 21–25")
    for block in seasons:
        if not isinstance(block.get("value"), str) or len(bytes.fromhex(block["value"])) != 124:
            raise ValueError("Each season must contain exactly 124 bytes")
    extra = schedule.get("extra", {})
    words = extra.get("words")
    if extra.get("block") != 28 or extra.get("parameter") != 50 or not isinstance(words, list):
        raise ValueError("Invalid tariff extra-data region")
    if len(words) != 29 or any(type(word) is not int or not 0 <= word <= 65535 for word in words):
        raise ValueError("Expected 29 valid tariff extra-data words")


def season_words(block):
    payload = bytes.fromhex(block["value"])
    return [int.from_bytes(payload[i : i + 2], "big") for i in range(0, 124, 2)]


def decode_season(value):
    payload = bytes.fromhex(value)
    if len(payload) != 124:
        raise ValueError("Expected 124-byte season")
    return {
        "start_month": payload[0],
        "start_day": payload[1],
        "second_month": payload[2],
        "second_day": payload[3],
        "events": [
            {
                "slot": (i - 4) // 6,
                "hour": payload[i],
                "minute": payload[i + 1],
                "unused": payload[i + 2],
                "days_of_week": payload[i + 3],
                "mode": payload[i + 4],
                "mode_data": payload[i + 5],
            }
            for i in range(4, 124, 6)
            if any(payload[i : i + 6])
        ],
    }
