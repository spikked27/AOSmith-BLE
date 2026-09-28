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
MODES = {"Electric": 1, "Hybrid": 4, "Heat pump": 5}
MODE_NAMES = {1: "Electric", 2: "Vacation", 3: "Guest", 4: "Hybrid", 5: "Heat pump"}
SETPOINT = (11, 0)
MODE = (11, 15)
AVAILABILITY = (27, 23)
FAULT = (2, 7)
# Conservative initial UI range; do not silently expand the device limit.
MIN_TEMP_F = 95
MAX_TEMP_F = 140
