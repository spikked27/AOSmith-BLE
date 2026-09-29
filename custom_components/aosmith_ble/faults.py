"""Short fault labels for the next-generation profile's current-fault byte.

Derived from iCOMM 14.1.0 modules 1422 (low-byte parser) and 1489
(catalog selected by nextGenHeatPumpFaultCodes). Not a fault history or
an assertion that every catalog entry is supported on every heater.
"""

FAULTS = {
    0: "No fault reported",
    1: "Tank not full / dry fire",
    2: "Water overtemperature",
    3: "Upper tank sensor failure",
    4: "Lower tank sensor failure",
    5: "Controller software failure",
    6: "Processor failure",
    7: "Display software failure",
    8: "Display hardware failure",
    9: "Supply voltage fault",
    20: "Communication failure",
    21: "Upper heating element fault",
    22: "Lower heating element fault",
    23: "Third heating element fault",
    24: "Fourth heating element fault",
    25: "Heat pump sensor fault (25)",
    26: "Heat pump sensor fault (26)",
    27: "Heat pump sensor fault (27)",
    28: "Ambient sensor failure",
    29: "Temperature sensor 7 fault",
    30: "Temperature sensor 8 fault",
    31: "Water leak detected",
    32: "Leak sensor disconnected",
    33: "Anode short circuit",
    34: "Water not detected",
    35: "Flame sensor short circuit",
    36: "Weak flame signal",
    37: "Flame sensing fault",
    38: "Ignition failure",
    39: "Transformer voltage fault",
    40: "Flammable vapor detected",
    41: "Tank temperature warning",
    42: "Clock not set",
    43: "Flow switch state fault",
    44: "Anode depleted",
    45: "Battery low (45)",
    46: "Water shutoff valve fault",
    47: "Smart valve fault",
    48: "Battery low (48)",
    80: "Air filter needs cleaning",
    81: "Condensate fault",
    82: "Compressor cycling too often",
    83: "Compressor pressure low",
    84: "Compressor fault",
    85: "Discharge temperature high",
    86: "Fan fault",
    100: "Setpoint knob out of range",
    101: "Upper thermostat fault",
    102: "Lower thermostat fault",
    200: "Flue overtemperature cutoff",
    201: "Air intake blocked",
    202: "Exhaust blocked",
    203: "Blower activation unconfirmed",
    204: "Gas pressure low",
    205: "Software / configuration key mismatch",
    206: "Anode module disconnected",
    207: "Safety controller disconnected",
    208: "Input/output module missing",
    209: "Condensate blockage",
    210: "Self-test completed",
    211: "Blower speed feedback missing",
    212: "Upper temperature probe fault",
    213: "Combustion controller hardware fault",
    214: "Combustion controller software fault",
    215: "Gas controller calibration fault",
    216: "Gas valve circuit fault",
    217: "Motorized throttle fault",
    218: "Water not detected by anode module",
    219: "External anode short circuit",
    220: "Anode module failure",
    221: "Reset lockout",
    222: "Configuration key missing",
    223: "Display missing",
    224: "Controller version incompatible",
    225: "Display software outdated",
    226: "Powered anode circuit fault",
    227: "NFC key version incompatible",
}


def fault_details(raw):
    """Keep unknown codes visible and retain the complete word for diagnostics."""
    code = raw & 0xFF
    details = {
        "fault_code": code,
        "description": FAULTS.get(code, f"Unknown heater fault ({code})"),
        "clock_not_set": code == 42,
        "raw_fault_register": raw,
        "raw_hex": f"{raw:04X}",
    }

    if code == 42:
        details["recommended_action"] = (
            "Connect the heater to the Internet using the official iCOMM app to restore its clock. "
            "Then reconnect Bluetooth and check that this error clears. "
            "If it persists, follow the manufacturer's clock setup instructions."
        )
    return details
