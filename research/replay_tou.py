"""Offline transcription of iCOMM 14.1.0's tariff event generator.

Research only: no Bluetooth, network access, or heater writes. Input is the
app's normalized touEvents list, not a bill or raw utility tariff. See
ONBOARDING_AND_TOU.md for evidence, limitations, and the illustrative fixture.
"""

import argparse
import json
import math
from pathlib import Path

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
            raise ValueError("Fixture requires a positive weekday price range for every season")
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


def ble_frame_bodies(block, payload):
    """14740/14743–14747, before transport adds packet CRC. Preserve its tail omission."""
    words = [payload[index : index + 4] for index in range(0, len(payload), 4)]
    words.pop()
    header, words = words[:2], words[2:]
    bodies = [f"BD400A{block:02X}00{''.join(header)}"]
    for index in range(0, len(words) - 5, 6):
        bodies.append(f"BD4012{block:02X}{index + 2:02X}{''.join(words[index : index + 6])}")
    bodies.append(f"BDA007{block:02X}3E01")
    return bodies


def replay(data):
    result = {"input_description": data.get("description"), "hardware_verified": False, "preferences": {}}
    for name, preference in PREFERENCES.items():
        events = make_events(data["touEvents"], preference)
        blocks = encode_seasons(events)
        result["preferences"][name] = {
            "schedule_preference": preference,
            "ble_preference_word": BLE_PREFERENCE_WORDS[name],
            "events": [{**event, "hex": encode_event(event).hex().upper()} for event in events],
            "season_blocks": blocks,
            "ble_season_frames_without_crc": [
                frame for block in blocks for frame in ble_frame_bodies(block["block"], block["value"])
            ],
        }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    print(json.dumps(replay(json.loads(args.input.read_text())), indent=2))
