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
3. `setEssentialParams` generator #13493 invokes `setClock`. A connection whose
   app profile is a next-generation enum skips it. The profile comes from the
   registered-device record, not directly from the physical model number; the
   owner's actual app record has not been retrieved. This guard was checked in
   bytecode as well as the decompiler output.
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


## Paired availability observations — 0.3.2.dev2

The owner supplied current iCOMM and official HA screenshots at 22:23 EDT on
September 28. iCOMM showed two red arc segments and one blue segment; the official
HA availability sensor showed 50%, updated 14 seconds earlier. The most recent
BLE diagnostic at 22:19:49 contained raw 0, also observed at 22:00, 22:08 and 22:14,
with valid responses and fault 0. These are close-time observations, not an atomic
cross-transport capture. Earlier three-red-bar app imagery at 21:18 was near raw
5 captures at 21:24/21:27. Together they support this explicit HPS10-80H45DV / 6.4
option: raw 0 → Medium/50%, raw 5 → High/100%.

The normal five-level arithmetic would incorrectly show 0% for the observed
Medium condition. A new `hps10_observed` scale uses only the two observed codes;
all others return unknown. It is opt-in because the integration does not identify
model/firmware automatically and other iCOMM devices may differ. Existing scales
remain unchanged. The category attribute clarifies that 50% is a status label,
not a measured tank-volume fraction. A future recovery/Low observation can refine
or disprove this mapping; Low is a valid cloud category, not inherently an error.

Energy progressed from 350.532 to 350.646 kWh across the captures; this supports
counter progression but does not independently calibrate its accuracy. No new
finite-duration or development-upgrade validation was supplied: the diagnostics
still identify installed version 0.3.1. The new code passes 129 local tests.


## Release review — 1.0.0

This section supersedes earlier development-only UI and scale choices above.
The release removes speculative linear/inverted scales, duplicate diagnostic
sensors and their configuration switches. HPS10 observed categories remain
explicitly selected. Vacation becomes one selection of days that both enters
the mode and starts its countdown. Electric's finite duration is restricted to
the model manual's 1–7 days. Debug buttons default disabled, including a one-time
upgrade migration. Core temperature/energy/countdown reads are always enabled.

### Is Low availability an error, or -5?

The product-linked owner's manual, printed page 25, lists **Not Enough Hot Water**
under **No Error Code Displayed**, with usage, leaks and mode among possible causes.
That supports treating availability separately from a heater fault, not inventing
a fault when a new availability code appears. Some manufacturer material describes
low-hot-water alerts; an app alert does not establish an error-register code.

The inspected next-generation APK fault catalog has no Low availability entry.
The WATER_AVAILABLE parser takes the low byte, then `hexToInt` uses
`parseInt(value, 16)` without sign extension. A relevant source search found no
mapping from -5 to Low. A separate literal -5 in unrelated code is a bit mask.
Signed -5 remains a hypothesis, not a supported conversion: 0xFB would parse as
251, while 0xFFFB would also yield low byte 251. Both the full raw word and byte
are retained in diagnostics; neither is mapped to Low or an error in this release.

Sources: [owner's manual, printed page 25](https://www.aosmithatlowes.com/media/1712/2000604721.pdf)
and the local iCOMM 14.1.0 next-generation parser/helper/fault catalog described above.
No additional water depletion or hardware experiment was requested.


## 1.1.0 correction: shrinking setpoint maximum and final UI

The owner reported that lowering 125°F to 124°F also lowered the UI maximum to
124°F, blocking a return to 125°F. The 1.0.0 fallback explicitly used the current
setpoint as a ceiling when maximum data was unavailable; it could produce exactly
this failure. This supersedes the earlier decision to treat that fallback or
register 1:43 as an established remote safety allowance for this profile.

Version 1.1.0 uses the manufacturer's documented 95–150°F HPS10 range, independent
of current setting and register 1:43. It still checks Vacation mode live and
requires exact write readback. The register is retained in manual diagnostics
for investigation, not written or used to impose a moving limit. No change to
firmware safety controls is attempted. Hardware acceptance of values above 125°F
has not yet been verified; failures will remain explicit instead of being called
successful writes.

The requested UI now follows active Vacation/Guest mode, defaulting HA mode-entry
to 7/1 days respectively. Other modes show Off. Availability uses observed HPS10
0→50% and 5→100% directly, with no calibration option. Unknown codes remain unknown.
Retired entity-registry entries are removed without issuing a recorder purge.

Tariff restoration was withdrawn by the owner. There is no tariff request/cache
or programming flow. An offline heater cannot receive new tariff data from the
service; the currentness of stored schedules, price data and holidays is not
established. Clock fault 42 includes recommended Internet/iCOMM recovery steps,
but clearing that fault is not proof of a current tariff or correct timezone.


## 1.1.1 availability correction

At September 28 23:52:41 and 23:52:52 EDT, version 1.1.0 received
`DB02091B17000A8006`: raw availability 10, with valid checksum and fault 0.
The owner then instructed the mapping 10=High/100%, 5=Medium/50%, 0=Low/0%.
This replaces the earlier 0=Medium, 5=High hypothesis derived from observations
at different times. The app/official-HA screenshots did not prove that hypothesis.

The release implements the owner's specified mapping. The 0/5/10 wire readings
are captured, while their categorical interpretation is not an independently
confirmed APK enum. Unknown values remain unknown, and Low does not set Error
status. Neither -5 nor 251 is assigned an availability category. Additional
comparisons may refine the interpretation; the raw data is preserved.


## Energy usage preference investigation — October 5, 2026

The iCOMM 14.1.0 APK labels three slider positions **More Hot Water**, **More
Savings**, and **Most Savings**. Its Most Savings confirmation explicitly warns
that this preference may cause the user to run out of hot water. The explanatory
text ties the preference to energy use during different periods of a rate plan.
This supports a possible explanation for insufficient recovery during an
expensive period; it does not establish the cause of any particular shortage.

The wire encoding differs from the cloud enum:

| App option | Slider | BLE serialized word | Cloud enum |
|---|---|---|---|
| More Hot Water | 0 | 1 | 1 |
| More Savings | 0.5 | 0 | 2 |
| Most Savings | 1 | 2 | 3 |

Module 1417's `convertUserPref` and serializer #14688 establish the wire words.
Module 1402's `USER_PREFERENCE` defines the separate cloud values. Do not send
cloud enum 3 to mean Most Savings over BLE.

**The next-generation address is unresolved.** Bytecode #14581
`getBlockAndIndex` selects block 0x1C (28), holiday start 0x32 (50) for profiles
other than the older `heatPump`. #14589 `getHolidayData` appends four extra words
to 25 holiday words: this puts the preference at 28:75 (0x1C:0x4B) in the
contiguous Wi-Fi payload. In contrast, Bluetooth #14586/#14587/#14588 appends
`formatExtraData` (#14591) items and uses each item's explicit parameter index;
that preference index is 113 (0x71), yielding 28:113. The next-generation module
1422 declares block 28 length 112, another reason not to assume 113 is valid.
The older named `setUserEnergyPreference` (#14614) writes 27:113; that is not a
verified HPS10 command and is not used here.

Version 1.1.2 adds **read-only** manual inspection of 28:75 and 28:113. These are
candidates, not exposed controls or decoded state. Normal polling is unchanged.
Capture before and after changing the preference in iCOMM, recording the exact
labels and waiting for the app to confirm application. A correlated change
would identify the storage candidate; a narrowly scoped BLE write with readback
and official-app verification must then establish whether preference-only
updates take effect without the app's full tariff re-upload/activation sequence.
No tariff, holiday, threshold, clock or enrollment writes are introduced.

## Follow-up: BLE preference experiment and clock trace — October 5, 2026

### What the app saves together

Following the actual EnergyUsePrefs Bluetooth save handler (#21288 in the
full decompiled listing) adds a key detail missing from the earlier register
comparison: the app first converts slider 0/0.5/1 to schedule preference 1/2/3
(module 2002), calls `timeOfUseToHex`, and only then calls `sendTOU` with the
original slider selection. `timeOfUseToHex` (#14497) calls `jsonToHex` (#14507),
which calls `makeEventsList` (#14517). Its map callback #14520 passes that
preference into `getDRn` (#14539) and writes the result into each event's `mode`.

These 1/2/3 values are therefore also schedule-generation inputs, not merely a
cloud enum. They must not be confused with module 1417's separate 1/0/2
serialized preference word. At the highest-priced period of a season whose
maximum/minimum price ratio exceeds 1.2, the generator produces mode 6, 7 or 8
for More Hot Water, More Savings or Most Savings respectively. The exact
controller response to each event code remains firmware behavior, not recovered
from this application. A lower price ratio caps the demand-response level.

The generator stores calendar start dates, day-of-week masks, hour/minute,
mode and modeData in season blocks 21–25 (0x15–0x19). It can insert mode-9
load-up events three hours before higher-priced periods when its base-price
check permits. These are *scheduled event times*, not the current clock time.
`sendTOU` #13465 sends holiday/preference data and then the season data; no
current date/time write appears in this sequence. The season writer ends each
block with a read of parameter 0x3E, not a timestamp write.

Thus the evidence-based model is: the app calculates and uploads calendar
instructions; the controller uses its own clock to execute them. The app does
not need to remain connected at every tariff boundary. The application's
ability to construct a schedule does not prove firmware activation or validate
clock accuracy. Changing the separate preference word alone might not rebuild
those stored modes; that is explicitly an experiment in version 1.2.0.

### Chosen first experiment

The user authorized a best-guess preference trial. The implementation uses the
Bluetooth path's 28:113 address, rather than automatically trying both candidates.
It requires a readable word in 0/1/2, saves and verifies the original value on
disk, sends one write, and checks readback. The restore control retains the first
backup across restarts. There is no automatic rollback after an ambiguous write,
no alternate-address fallback, and no claim that readback proves heating effects.
If this candidate is rejected, the result is useful evidence about the app's
apparent map inconsistency; it does not authorize silently selecting a new map.

### Clock: confirmed bytes and unresolved next-generation path

The only explicit heater clock constructor located in iCOMM 14.1.0 remains
`setClock` #14611. Its serializers #14678/#14679 take the phone's **local** date
and time using getMinutes/getHours/getDate/getMonth/getFullYear:

- Destination: block 26, starting parameter 3 (0x1A:0x03), two adjacent words.
- Payload order: minute byte, hour byte, then the two-byte packed calendar date.
- Packed date: `(year % 100) << 9 | month << 5 | day` (month 1–12).
- Example for 2026-10-05 18:53 local: payload `35 12 35 45`.
- No seconds, timezone identifier, UTC offset, or DST rule is serialized here.

The constructor assembles one multiword BD40 frame. This is a known *legacy*
command format, not an HPS10 command recommendation. Rechecked authoritative
Hermes bytecode #13456 offset 0xA6: it jumps past `setEssentialParams` unless the
profile is exactly `HEAT_PUMP`. #13493 calls remote-enable followed by `setClock`.
The profile reference is supplied by the connection callers; NEXT_GEN_HEAT_PUMP
is a distinct enum and is also used to select the newer temperature/mode map.
No next-generation replacement clock write was found in module 1422.

The follow-up also searched the full JS listing for Date/time/epoch/timezone
conversion paths and examined method identifiers in all six DEX files. The
AO Smith native classes were React Native application/activity/resources;
Bluetooth writes route through the BLE-PLX bridge. Identified native clock
methods belonged to Android/UI/libraries or Google's scheduler, not an AO Smith
clock API. No literal standard Current Time Service/characteristic UUID
(0x1805/0x2A2B) was found. This negative search is not proof that firmware exposes
no clock, or that another installed/updated app build behaves identically.

The manufacturer's current heat-pump Use & Care Guide 100379654 (March 2025),
printed pages 25 and 27, explicitly discusses setting time after disconnected
control/power conditions and documents battery-low code 048 with a replaceable
controller battery. The broader service handbook 2000620230, printed page 17,
contains the same battery/time note. This is family-level evidence of retained
time and Wi-Fi/Bluetooth association with setting time; it supplies no register
mapping or documented drift/DST resynchronization interval for the HPS10.
Sources:
https://assets.hotwater.com/damroot/Original/10009/100379654.pdf
https://assets.hotwater.com/damroot/Original/10017/2000620230.pdf

Consequences: Bluetooth time setting is a credible capability, and an internal
clock can continue running without the phone. It does not follow that every
connection synchronizes time, nor that the exposed legacy address is shared by
the HPS10. The owner's all-zero 26:3/4 reads do not identify a running RTC. The
remaining evidence includes the app's actual registered device profile and
normalized tariff data, plus the heater's stored schedule blocks. The detailed
follow-up below identifies these steps before traffic capture. If a capture is
needed, it must include official-app Bluetooth reconnect/tariff-save traffic
and a phone-local time reference; HA's own traffic log cannot see another
central device's writes. No next-generation clock write or automatic clock
synchronization is added in this release.

### Capture-version correction

The owner's October 5 diagnostic files ending 14 and 19 list downloaded custom
component 1.1.2, but both running diagnostics and the loaded manifest say 1.1.1.
Neither includes preference-candidate entries or corresponding transmitted read
frames. File 14 also contains an old September 29 extended snapshot, while file
19's snapshot stopped after a timeout. These are not evidence of unchanged
preference candidates. A full HA restart is needed to load and verify the new
runtime before the experimental test.

## Full onboarding and tariff reconstruction — October 5, 2026

[Onboarding, clock setting, and tariff reconstruction](research/ONBOARDING_AND_TOU.md)
traces QR/manual registration, device-record selection, first Bluetooth setup,
ordinary reconnect, initial tariff upload, preference changes, and separate
Wi-Fi provisioning. It corrects the assumption that the physical HPS10 model
alone identifies the app's clock branch: the cloud-provided `deviceType` is the
actual selector, and no onboarding alias to the legacy profile was found.

The follow-up includes an [offline generator](research/replay_tou.py) and
explicitly illustrative [Rate 195 input](research/rate195_illustrative_input.json)
and [all-preference output](research/rate195_illustrative_output.json). Preference
changes alter generated event modes, while the same input retains the same
time boundaries. In the fixture, both savings options retain DR1 from 19:00 to
22:00, and the minimum-price check places load-up at 03:00 before the 06:00 price
rise. These are reproducible app-algorithm results, not the owner's tariff
response or a heater readback.

The detailed report also records a bytecode-confirmed apparent tail omission
in the app's BLE season frame builder, the limits of clock/DST evidence, and
what can be learned before sniffing traffic. No production integration code,
version, or heater settings changed in this follow-up.
