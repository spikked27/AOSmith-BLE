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
# HPS10 manual permits 150 F; remote control still honors the reported maximum.
MIN_TEMP_F = 95
MAX_TEMP_F = 150
DEFAULT_MAX_TEMP_F = 140

VERSION = "0.3.2.dev1"
AVAILABILITY_SCALES = {
    "unverified": "Not calibrated",
    "five_levels": "0–5 levels (estimated 20% steps)",
    "percent_remaining": "0–100 percent remaining",
    "percent_used": "0–100 percent used (inverted)",
}
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
INSPECT_REGISTERS = {
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
