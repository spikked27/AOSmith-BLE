# Temperature limits, clock requirements and official integration comparison

Research date: September 29, 2026 UTC (September 28 in New York).
Scope: iCOMM 14.1.0 APK, current official HA integration and py-aosmith,
the HPS10-80H45DV product-linked owner's manual, and prior redacted BLE results.
No hardware settings were changed during this research.

## Practical findings

| Feature | Does this integration need to set the heater's calendar clock? | Evidence / remaining limit |
|---|---|---|
| Temperature and operating mode | No clock step in the implemented protocol | App writes mode/setpoint directly; owner validated these controls |
| Readings and cumulative energy | No clock step | HA timestamps readings; cumulative energy is a counter |
| Vacation/Guest/timed Electric command | No date/time payload | App sends mode plus duration; finite expiry/power recovery still need physical testing |
| HA history and HA-owned automations | No | These use HA's clock/timezone; scheduled writes require HA and BLE to be available |
| Tariff lookup/programming | Removed from integration | Use the official iCOMM app |
| Heater-owned seasonal/weekday/holiday TOU | Correct heater-local date/time is required | Clock source, synchronization, DST and power-loss behavior remain unresolved |

The previous project-wide clock blocker was too broad. It belongs to reliable
offline **heater-owned scheduling**, not to completion of basic local control.
No clock button should be added until its next-generation protocol is identified.

## Maximum temperature: product capability versus remote allowance

The manual linked from the HPS10-80H45DV product page specifies a 95–150°F
setpoint range (printed page 21). A fixed 140°F integration ceiling was therefore
too restrictive when the heater advertises a higher permitted remote value.

The APK next-generation register map defines maximum setpoint at block 1,
parameter 43. Its parser combines the temperature word and converts C×256 into
Fahrenheit. Function #13507 selects that register/parser for the next-generation
profiles. UI function #18608 reads `temperatureSetpointMaximum`; #18610 builds
the selectable temperatures from that maximum. The UI's increase-maximum help
directs the user to raise the setting on the physical heater, after which the
app reflects the new remote maximum. This is a real setpoint adjustment, not a
separate harmless UI slider setting. No remote maximum override was established.

The official integration's `AOSmithWaterHeaterEntity.max_temp` returns
`device.status.temperature_setpoint_maximum`. py-aosmith maps that from the
cloud field `temperatureSetpointMaximum`. It does not fix every heater to 140°F.
Its `update_setpoint` submits a value to the cloud; that does not establish a
BLE method for increasing the heater's configured remote maximum.

The owner's recent BLE maximum word was 0x33AB, decoding to approximately 125°F.
This explains the current integration limit. It does not establish that an
online app currently reports the same maximum. If the app really offers 140°F
at the same time, compare fresh BLE and app/cloud values before assuming they
are equivalent. Do not bypass a reported limit just because the product can
operate at a higher temperature.

Development changes now allow reported maxima through 150°F, retain the existing
fallback no higher than the current setting (capped at 140°F) when maximum data
is missing/invalid, and always request the
maximum independently of optional diagnostic reads. There is no automatic
setpoint increase and no write to the maximum register.

## Clock trace through the APK

1. Named function #14611, `setClock`, writes older-profile block 26, words 3–4.
   The associated serializers use local minute/hour and a packed calendar date
   (two-digit year, month and day). They do not send an IANA timezone name.
2. Connect generator #13456, offsets 0x8E–0xAA, compares the current device profile
   with `heatPump`. Only that older profile calls `setEssentialParams`.
3. `setEssentialParams` generator #13493 invokes `setClock`. The next-generation
   connection path skips it. This guard was checked in bytecode as well as the
   decompiler output.
4. Next-generation module 1422 exposes setpoint/mode/status registers in blocks
   1, 2, 11, 27 and 28. No replacement clock setter was found in that module.
5. BLE TOU upload generator #13465 calls the holiday/preference writer and then
   the season writer. It does not contain a date/time synchronization step.
   `formatExtraData` #14591 serializes preference, price thresholds and preheat
   lead time; that last value is a duration, not the current time or timezone.
6. Searches of the six DEX method tables found the `setClock` native method in
   Google's data-transport scheduler builder. It is not a heater-setting method.
   UI date-picker timezone strings likewise are not evidence of a heater payload.

These findings do not prove that no clock command exists in firmware. The
controller/radio firmware and the cloud service's internals are not contained
in the inspected application sources. Cloud provisioning, network time, an
internal RTC or another command remain possibilities, not established facts.

### Next-generation clock fault

The next-generation fault catalog is module 1489 (selected by module 1488's
`nextGenHeatPumpFaultCodes` export). It contains fault 42, **Real Time Clock not
set**. This is relevant to this heater family; other clock errors elsewhere in
the app belong to commercial families and should not be copied across models.

The owner's captures showed current fault 0. Absence of fault 42 does not tell
us the clock's actual date, accuracy or timezone. Likewise the four zero reads
from older-profile candidate words 26:3–4 do not prove the heater lacks a clock,
needs resetting, or supports writing those addresses. Repeating identical reads
will not resolve the protocol mapping.

## Vacation is a device countdown

The HPS10 manual (printed page 19) describes a duration timer and return to the
previous mode with **nine hours remaining**, allowing recovery before arrival.
It offers 1–99 days or permanent operation. APK #14699 writes mode and duration
to 11:15; dedicated registers 11:17–19 report the respective remaining days.
The mode dialog offers Vacation 100 as an indefinite sentinel, not 100 days.

This supports native countdown control without adding clock synchronization or
an HA replacement expiry timer. It does not prove that a countdown survives
loss of power. HA should not promise an exact return timestamp calculated as
now plus days×24 hours.

The manual describes Electric duration as 1–7 days, while APK dialog #18696's
generic day options are 1–99 (Vacation adds its indefinite sentinel and Guest
has a separate 1–7 list). This discrepancy requires model/firmware acceptance;
the app's generic UI must not be called proof that HPS10 accepts 99 Electric days.

## What the official integration adds—and does not establish

The inspected HA integration uses py-aosmith 1.0.18 and cloud polling. Setup and
coordinators get device status and energy data. The water-heater entity controls
setpoint/modes and treats Vacation as away mode. Turning away mode off chooses
the first supported mode in Hybrid, Heat Pump, Electric order; it does not
demonstrate a local previous-mode restoration command.

py-aosmith supports a `days` argument for day-selecting modes and defaults it to
100 when omitted. The standard HA water-heater away action does not provide a
days control. No clock synchronization, timezone-setting or BLE transport exists
in the inspected official control path. Its broader diagnostics query includes
TOU data, but that is not an implemented schedule-upload method in the client.

The library converts cloud LOW/MEDIUM/HIGH availability into 0/50/100, or inverts
a numeric cloud percentage. Neither establishes a conversion for BLE raw code 5.
That observation still cannot justify a universal five-level percentage scale.

## Sources and reproducibility

- [HPS10-80H45DV manufacturer product page](https://www.aosmithatlowes.com/products/water-heaters/electric-water-heaters/hps10-80h45dv/)
- [Product-linked owner's manual, 2000604721 Rev. B](https://www.aosmithatlowes.com/media/1712/2000604721.pdf), printed pages 19–23
- [Official HA water heater entity](https://github.com/home-assistant/core/blob/dev/homeassistant/components/aosmith/water_heater.py), plus manifest, setup, coordinator and sensor modules, inspected September 29
- [py-aosmith client at inspected commit](https://github.com/bdr99/py-aosmith/blob/8d4eb7f1b75e1898227810ff9d007d8fd3291434/py_aosmith/client.py), plus models and query definitions
- Local user-supplied iCOMM 14.1.0 APK: Hermes bytecode/decompiler cross-checks
  referenced above. APK contents and private diagnostic files are not redistributed.

115 automated tests pass locally, including reported temperature bounds at
125/140/150°F and keeping maximum reads enabled when diagnostics are disabled.
These are software tests; no new maximum-temperature, duration-expiry, clock,
DST or heater-owned schedule test was performed on hardware during this research.


## Finalization review — 0.3.2.dev1

Tariff HTTP lookup, cached preview, configuration steps and entity were removed.
Old caches are cleared during setup and retired entities are disabled without
purging history. Heater schedules are unchanged. No clock entity or writer was
added: fault 42 appears in the consolidated Error status indicator. The low-byte
fault parser was rechecked directly in module 1422. Catalog descriptions do not
establish that every fault applies to every model.

The official availability conversion was rechecked in `parse_hot_water_status`:
LOW → 0%, MEDIUM → 50%, HIGH → 100%; numeric API values → 100 minus value.
The APK's BLE WATER_AVAILABLE parser returns the low byte without that conversion.
Therefore raw 5 cannot yet be labeled High/100% from official-integration code.
A paired shower-time raw reading and app indication remains the next evidence.
