"""Constants for the experimentally verified next-generation iCOMM protocol."""

DOMAIN = "aosmith_ble"
NAME = "AO Smith Local BLE"
SERVICE_UUID = "69400001-b5a3-f393-e0a9-e50e24dcca99"
NOTIFY_UUID = "69400002-b5a3-f393-e0a9-e50e24dcca99"
WRITE_UUID = "69400003-b5a3-f393-e0a9-e50e24dcca99"
CONF_IDENTIFIER = "pairing_identifier"
CONF_PIN = "pin"
CONF_INTERVAL = "poll_interval"
DEFAULT_INTERVAL = 30
MODES = {"Electric": 1, "Vacation": 2, "Guest": 3, "Hybrid": 4, "Heat pump": 5}
MODE_NAMES = {1: "Electric", 2: "Vacation", 3: "Guest", 4: "Hybrid", 5: "Heat pump"}
SETPOINT = (11, 0)
MODE = (11, 15)
AVAILABILITY = (27, 23)
FAULT = (2, 7)
# Documented HPS10 setpoint range. Register 1:43 is not used as a write ceiling.
MIN_TEMP_F = 95
MAX_TEMP_F = 150

VERSION = "2.2.0"
CONF_ENERGY_PREFERENCE = "enable_experimental_energy_preference"
ENERGY_PREFERENCE = (28, 75)
CLOCK = (26, 3)
ENERGY_PREFERENCES = {"More Hot Water": 1, "More Savings": 0, "Most Savings": 2}
DEFAULT_MODE_DAYS = {1: 1, 2: 7, 3: 1}


def clean_options(options):
    """Keep supported controls and a deliberately selected cached rate plan."""
    result = {CONF_INTERVAL: options.get(CONF_INTERVAL, DEFAULT_INTERVAL)}
    tariff = options.get("tariff")
    if isinstance(tariff, dict) and tariff.get("schema_version") == 1:
        result["tariff"] = tariff
        result["tariff_preference"] = options.get("tariff_preference", "More Hot Water")
    return result


ENERGY = (27, 7)
MAX_SETPOINT = (1, 43)
REMOTE_SETPOINT = (11, 6)
VACATION_DAYS = (11, 17)
GUEST_DAYS = (11, 18)
ELECTRIC_DAYS = (11, 19)
TIMED_MODE_REGISTERS = {
    1: ("electric_days", ELECTRIC_DAYS),
    2: ("vacation_days", VACATION_DAYS),
    3: ("guest_days", GUEST_DAYS),
}
HOT_WATER_PLUS = (11, 20)
UTILITY_OVERRIDE = (27, 3)
CTA_PRESENT = (27, 25)
ADVANCED_LOAD = (28, 13)
UTILITY_ENROLLMENT = (28, 109)
OPTIONAL_REGISTERS = {
    "maximum_setpoint": MAX_SETPOINT,
    "remote_setpoint": REMOTE_SETPOINT,
    "vacation_days": VACATION_DAYS,
    "guest_days": GUEST_DAYS,
    "electric_days": ELECTRIC_DAYS,
}
# Read-only capture; grid energy units and clock mapping remain unverified.
# APK TOU paths disagree on the next-generation preference offset. The explicit
# owner capture rejects 28:113 but reads 28:75; use the contiguous candidate.
ENERGY_PREFERENCE_CANDIDATES = {
    "energy_preference_candidate_contiguous": (28, 75),
    "energy_preference_candidate_ble": (28, 113),
}
INSPECT_REGISTERS = {
    **ENERGY_PREFERENCE_CANDIDATES,
    "clock_candidate_low": (26, 3),
    "clock_candidate_high": (26, 4),
    **OPTIONAL_REGISTERS,
    "utility_override": UTILITY_OVERRIDE,
    "cta_present": CTA_PRESENT,
    "advanced_load": ADVANCED_LOAD,
    "utility_enrollment": UTILITY_ENROLLMENT,
    "hot_water_plus": HOT_WATER_PLUS,
    **{f"electric_power_usage_{2 - i}": (27, 7 + i) for i in range(3)},
    **{f"grid_present_energy_{2 - i}": (27, 10 + i) for i in range(3)},
    **{f"grid_total_energy_{2 - i}": (27, 13 + i) for i in range(3)},
}
