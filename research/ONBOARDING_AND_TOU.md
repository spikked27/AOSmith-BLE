# iCOMM onboarding, clock setting, and tariff schedule reconstruction

Research date: October 5, 2026. Scope: the supplied iCOMM Android 14.1.0 APK,
Hermes bytecode version 96. APK SHA-256:
`18cb2b977c049a9c4b4cf38a92dd0ce7fc57dc42b9b51f63fee17bd009992c7e`.
Function numbers below identify that exact bundle, not stable public API names.

This investigation made no heater writes. The accompanying program is an
offline transcription of recovered application logic. It is not a production
schedule writer or an execution of the installed app against a heater.

## Findings

1. Changing the savings preference regenerates the tariff's scheduled event
   modes, then uploads holiday/preference information and season blocks. For a
   fixed tariff and generator configuration, all three preferences use the same
   time boundaries and load-up times; their demand-response levels can differ.
2. The only explicit heater-clock setter found writes phone-local time and date
   to legacy block 26, parameters 3–4. The common Bluetooth connection routine
   calls it when the app's device profile is exactly `HEAT_PUMP`. This is not
   restricted to initial enrollment or the first tariff save.
3. That profile comes from the registered-device record. A physical model name
   alone does not prove which branch the app takes. The owner's actual app
   record has not been retrieved. No onboarding alias from a `NEXT_GEN_*`
   profile to `HEAT_PUMP` was found.
4. The normalized tariff prices come from the app's cloud service. Therefore
   reproducing the generator is possible offline, but claiming an exact match
   to the owner's saved schedule requires the actual input or a heater readback.

## New-heater workflow, from registration to tariff upload

| Stage | Traced path | Clock implications |
|---|---|---|
| Identify/register heater | QR serial handler #20727 or manual handler #21018 → registration wrapper #20707 → Redux registration #15264 | Sends registration details to the cloud. No BLE clock command here. |
| Refresh device record | #15264 calls `getDevices`; #14831 queries `DEVICE_INFO_QUERY` (`devices`), then dispatches returned device objects | Supplies `deviceType`, DSN, and junction ID. Existing Bluetooth records may be retained during a refresh; this does not substitute a legacy type. |
| Select current heater | Module 1430 `getCurrentDevice` #15007 selects by junction ID; unit conversion #15003 copies device fields | No replacement of `deviceType` was found. |
| Choose connection | `ConnectionMethod` #22159; Bluetooth setup and permission screens #22445/#22462 | Ordinary setup proceeds to Bluetooth connection. A TOU setup route proceeds through `SendSchedule`. |
| Enter Bluetooth connection screen | `BluetoothSetupTurnOn` #21629, effect #21634 | Passes DSN, asset ID, junction ID, and the device record's type to `forceConnection`. The derived asset ID is an identity value, not a timestamp. |
| Scan and select profile | `forceConnection` #13452 / `scanAndConnect` #13451; scan helper #13450 | Stores the supplied profile and scans for `iCOMM-<dsn>`. No clock payload or legacy-profile default found. |
| Connect and authenticate | `establishConnection` #13461 → BLE connect, MTU request, GATT discovery, service selection, PIN/session setup | Session #14560 exchanges pairing ID/enrollment, challenge, and HMAC messages. Its first-enrollment branch contains no date/time field. |
| Set essential parameters | Outer `connect` #13456 → #13493 **only if profile equals `HEAT_PUMP`** | Remote-enable followed by `setClock` #14611. Other profile values skip this call. |
| Finish ordinary setup | `BluetoothSetupComplete` #22499 can navigate into TOU setup | No additional first-setup clock write found. |
| Select utility/tariff | Tariff selection supplies a tariff ID; `getTimeOfUseData` #21363 queries `tariffAndHoliday` | Returns normalized `touEvents` and holidays. Those event timestamps are calendar instructions, not current time. |
| Generate/send first tariff | `SendSchedule` module 2046, callback #21618 → `timeOfUseToHex` #14497 → `sendTOU` #13465 | Generates with preference 1/2/3, sends holiday/extra data, then seasons. No separate clock setter in this sequence. |
| Record success | #21621 updates rate-plan metadata and navigates to the applied screen | Cloud/UI bookkeeping is not evidence of a clock synchronization command. |
| Change preference later | `EnergyUsePrefs` Bluetooth handler #21288 → `timeOfUseToHex` → `sendTOU`; #21295 enters setup if a connection is needed | Rebuilds the schedule. A new legacy-profile connection may also run the common clock routine; the preference handler itself does not. |

The connected status is set inside connection establishment, before the outer
function finishes its essential-parameter work. Consequently, this code does
not establish a strict “clock write completes before the TOU screen starts its
upload” ordering. The important verified fact is the conditional call site.

The enum and configuration tables keep `HEAT_PUMP`, `NEXT_GEN_HEAT_PUMP`,
`NEXT_GEN_HEAT_PUMP_BEST`, and `NEXT_GEN_HEAT_PUMP_120V` distinct. Module 1498's
legacy heat-pump group contains only the first. The newer configuration also
advertises Bluetooth; the absence of a matching explicit clock call should not
be explained away by assuming those screens are Wi-Fi-only.

### Separate Wi-Fi setup path

The access-point helper in module 2105 scans networks and sends credentials to
`/wifi_connect.json` at the heater's local setup address. Its constructed
request contains network selection and key data, not a date/time field.
`Connect` #22189 creates a `startConnectionTimestamp`, but tracing the consumer
shows that `isDeviceOnline` #22180 passes it to the cloud query as
`connectedAtStartTime`. It is a connectivity-check timestamp, not a recovered
local heater-clock command.

Wi-Fi TOU saving #14975 calls cloud `SET_TIME_OF_USE` with the junction ID, TOU
data, device type, and edit data. The app bundle cannot establish what cloud
services or controller/radio firmware do after receiving that request. Network
time, factory initialization, and other firmware behavior remain possibilities,
not findings from this APK.

## What each savings option generates

Three related representations must be kept separate:

| UI option | Slider | Schedule-generation preference | Separate explicit BLE preference word |
|---|---:|---:|---:|
| More Hot Water | 0 | 1 | 1 |
| More Savings | 0.5 | 2 | 0 |
| Most Savings | 1 | 3 | 2 |

Module 2002 supplies the slider-to-generator mapping. Module 1417 supplies the
separate word mapping. The version 1.2.0 integration's experimental selector
writes that separate word only; it does **not** duplicate this schedule rebuild.
The previously documented explicit-BLE versus contiguous-payload address
disagreement is still unresolved.

### Price-to-event calculation

Functions #14539 (`getDRn`), #14540 (`calcDrnMax`), and #14541 (`calcDrn`) implement
the following for ordinary positive prices:

- Find minimum `m` and maximum `M` among the season's **weekday** input prices.
  The grouping key is the exact season-start month/day. Weekend prices are
  evaluated against those weekday bounds.
- If the event price `c <= m`, emit mode 0.
- Let the price-ratio cap be 1 if `M/m < 1.1`, 3 if `M/m > 1.2`, otherwise 2.
  Equality at either threshold takes the middle branch.
- Let `n = min(clamp(preference, 0, 3), cap)`.
- Calculate `slope = n / (M - m)`, `offset = -slope * m`, and
  `level = Math.round(slope * c + offset)`.
- Emit mode `5 + level` when the level is positive; otherwise emit 0.

At the seasonal maximum with a ratio above 1.2, the three choices therefore
emit modes 6, 7, and 8. For intermediate prices, they may emit the same mode.
With a ratio below 1.1, all three preferences have the same effective cap.
There is no universal three-entry schedule baked into the app: the actual
prices determine the result.

For a ratio above 1.2 and prices within the weekday range, define
`x = (c - m)/(M - m)`. Ignoring floating-point boundary effects, the bands are:

| Option | Mode 0 | Mode 6 (DR1) | Mode 7 (DR2) | Mode 8 (DR3) |
|---|---|---|---|---|
| More Hot Water | x < 1/2 | x ≥ 1/2 | — | — |
| More Savings | x < 1/4 | 1/4 ≤ x < 3/4 | x ≥ 3/4 | — |
| Most Savings | x < 1/6 | 1/6 ≤ x < 1/2 | 1/2 ≤ x < 5/6 | x ≥ 5/6 |

“DR1/2/3” describes the recovered numeric level, not a measured physical
response. The exact compressor, element, temperature, reserve, or hysteresis
behavior of these codes is not implemented in the recovered generator.
Mode 0 means the generator's baseline/no-positive-DR result; it does not mean
“heater off.” These are distinct from the user-selectable heater mode numbers.

The app does not clamp the final computed level again. Unusual input, such as
weekend prices above the weekday maximum, falls outside the table's stated
range. Negative/zero prices and malformed season data are not supported by the
offline research replay.

### Load-up timing

Module 1406 defaults to a three-hour lead. In #14521, every price event above
the seasonal minimum proposes a mode-9 load-up event three hours earlier. The
candidate is inserted only if #14524–#14527 determine that its time lies in a
minimum-price period for the same season and weekday mask.

This decision tests **price**, not the computed DR level or chosen preference.
It can insert a load-up before an event that subsequently has mode 0. It does
not mean “always preheat three hours before the afternoon peak.”

Two original-code quirks are retained in the replay: the base-price lookup uses
component-wise hour/minute comparisons, and subtraction crossing midnight
wraps the hour without moving the weekday mask or season date. The supplied
fixture uses whole-hour boundaries and does not cross midnight during load-up.

## Illustrative PSEG Long Island Rate 195 replay

The utility's published Rate 195 calendar has weekday peak hours 15:00–19:00,
super-off-peak 22:00–06:00 daily, and off-peak in the intervening hours. Weekends
and designated holidays have no afternoon peak. The published supply factors
are 60% / 100% / 174.19% of the monthly base in summer and 60% / 100% / 196.88%
outside summer. Summer covers June–September.

`rate195_illustrative_input.json` uses those factors normalized to base 1, with
season starts January 1, June 1, and October 1. **It omits delivery charges and
holiday encoding, is not the cloud's fetched tariff, and is not a readback of
the owner's heater.** Its purpose is to demonstrate the recovered algorithm
with a clearly specified, reproducible input.

The resulting ordinary weekday events are the same in each illustrative season:

| Effective local time | More Hot Water | More Savings | Most Savings |
|---|---|---|---|
| 00:00 | Baseline (0) | Baseline (0) | Baseline (0) |
| 03:00 | Load-up (9) | Load-up (9) | Load-up (9) |
| 06:00 | Baseline (0) | DR1 (6) | DR1 (6) |
| 15:00 | DR1 (6) | DR2 (7) | DR3 (8) |
| 19:00 | Baseline (0) | DR1 (6) | DR1 (6) |
| 22:00 | Baseline (0) | Baseline (0) | Baseline (0) |

Weekend events are 00:00 baseline, 03:00 load-up, 06:00 baseline/DR1/DR1,
and 22:00 baseline. There are no 15:00 or 19:00 weekend transitions in this
fixture. Holidays are intentionally not modeled.

At 03:00 the price is minimum, so the proposed preheat before the 06:00 rise is
accepted. The candidate before 15:00 would be at noon, when the price is above
minimum, so it is rejected. The candidate before 19:00 falls inside peak and is
also rejected. Both savings choices therefore retain DR1 during 19:00–22:00.
That is a plausible schedule-based explanation for continued evening savings
behavior; it is not proof of the owner's currently stored events or clock.

More Hot Water still emits DR1 during the peak. It does not disable TOU.

## Serialization and the Bluetooth upload

The path is `timeOfUseToHex` #14497 → `jsonToHex` #14507 → `makeEventsList`
#14517 → `ratesToSeasons` #14543 → `seasonToHex` #14531.

- All-days ranges 0–6 are split into weekday 0–4 and weekend 5–6 groups.
- Wire weekday mask: Sunday bit 0 through Saturday bit 6; weekdays `3E`,
  weekends `41`.
- Each event has six bytes: hour, minute, unused zero, weekday mask, mode,
  modeData zero.
- Each season has four header bytes (start month/day, second month/day zero)
  and twenty event slots. The serializer emits 124 bytes per season.
- There are five season blocks, decimal 21–25 (`15`–`19` hex), including zero
  padding for unused slots and seasons. No current-time value is in those bytes.

For example, weekday 15:00 is `0F 00 00 3E 06 00`,
`0F 00 00 3E 07 00`, or `0F 00 00 3E 08 00`, depending on preference.
Weekday 03:00 load-up is `03 00 00 3E 09 00` for all three.

`sendTOU` #13465 sends holiday/extra data first and season data second.
The holiday converter #14547 matches returned `calendarEventId` values against
the static `knownHolidays` table in module 1413, assigns parameter indexes
starting at 50, and adds zero entries. That table encodes recurring calendar
rules; it does not read the phone's current time. Preference is not an input to
the holiday lookup. The companion extra-data formatter #14591 adds preference,
price thresholds, and the load-up duration, also without current time.

`sendSeasons` #14728 calls `buildFrames` #14740 directly with each season value.
Each block ends with `BD A0 07 <block> 3E 01` before transport CRC, a read of
parameter 62. Whether reading that parameter also triggers firmware validation
or activation is unknown. A read opcode alone does not establish the absence
of a firmware side effect or precisely when new schedules take effect.

### Apparent omission in the app's BLE frame builder

This is a static code finding, not a hardware-observed failure:

1. The 124-byte season is split into 62 two-byte words.
2. `buildFrames` pops one word, then removes two header words, leaving 59.
3. `buildRegularFrames` #14744/#14745 emits only complete six-word chunks.
4. Nine chunks write 54 words: **18 events**, after the separate header write.
5. The last two event slots (parameters 56–61) are not written by that path.

The template contains a `crc` property, but `seasonToHex` does not serialize it.
The separate Wi-Fi `buildBlock` path adds its own trailing data/CRC and is not
the input to this BLE builder. The pop and chunk behavior were confirmed in
original bytecode, rather than inferred only from decompiled syntax.

The fixture has ten events per used season, so all its nonzero events fit in
the eighteen written slots. The omission could still matter for clearing old
tail events or larger tariffs; firmware treatment is unknown. The replay emits
the observed frame bodies faithfully, without packet CRC or transmitting them.

## Clock bytes and what remains unresolved

`setClock` #14611 and serializers #14678/#14679 use JavaScript local-time date
methods. The destination is block `1A`, starting parameter `03`, with two words:

| Payload bytes | Meaning |
|---|---|
| 0 | Phone-local minute |
| 1 | Phone-local hour |
| 2–3 | Packed calendar date, most-significant byte first |

The packed date is `(year % 100) << 9 | month << 5 | day`, with month 1–12.
For 2026-10-05 18:53 local, the four payload bytes are `35 12 35 45`.
There are no seconds, timezone ID, UTC offset, or DST-rule bytes in this setter.

The bytecode guard at #13456 offset `0xA6` skips essential parameters unless
the profile equals `HEAT_PUMP`. Both initial and later connections can reach
this common routine. Thus a battery-backed RTC plus phone synchronization on
connection is directly supported for that profile. If the actual registered
record of a newer physical heater says `HEAT_PUMP`, it reaches this path too;
that record must be observed before claiming it does or does not.

For records carrying one of the next-generation enums, no replacement explicit
clock write was found in the traced onboarding, connection, tariff-save,
preference-change, or Wi-Fi credential paths. The broader search covered
date/time conversions in the full JS bundle and native identifiers in six DEX
files. Found native clock names belonged to Android/UI/support libraries, not
a separate AO Smith clock bridge. No literal standard Bluetooth Current Time
Service/characteristic UUID was found. These searches cannot establish that no
other firmware command or other app version implements synchronization.

Manufacturer guide 100379654, printed pages 25 and 27, discusses time setting
in connection with disconnected Wi-Fi/Bluetooth conditions and a replaceable
controller battery (fault 048). It supports the retained-clock explanation at
the product-family level, but supplies no verified HPS10 clock register or DST
algorithm. A battery can preserve a clock; it does not by itself establish
long-term accuracy or automatic seasonal clock changes. A controller could
implement DST using calendar date internally, but that has not been recovered.

## Reproduce and narrow the remaining gap

Run from the repository root with Python 3.13:

```sh
python research/replay_tou.py research/rate195_illustrative_input.json
```

The checked-in output includes all three event lists, event bytes, all five
124-byte season payloads per preference, and BLE season frame bodies before
CRC. It does not include the holiday/extra-data writer or make any connection.
The replay uses the app's default three-hour lead and 1.1/1.2 thresholds only.

Validation: 5,405 mode calculations matched the recovered JS control flow,
including threshold equality and flat-price cases. The comparison restored
local register declarations and two malformed decompiler call expressions,
whose real argument counts were checked against Hermes bytecode. Fixture
reproducibility, event/payload sizes, BLE frame offsets, and coverage of the
first 112 payload bytes were also checked. This verifies the transcription's
tested calculations and serialization, not installed-app or firmware behavior.

Before traffic capture, the useful missing evidence is:

1. The app's actual `deviceType` value and normalized tariff response for this
   registered heater. These distinguish the clock branch and allow an exact
   all-preference replay. Registration/account identifiers should stay private.
2. Readback of stored season blocks 21–25 and holiday/extra data to compare with
   generated bytes. Their readability on this heater must be confirmed. The
   existing integration's **Inspect extended registers** action does not yet
   dump those full schedule blocks, so its current diagnostics cannot answer
   that comparison.
3. If those leave the clock source unresolved, a capture of the official app's
   Bluetooth connection and tariff-save writes, annotated with phone-local
   time and app version, can settle what actually crosses the link. HA's own
   BLE log cannot see another central device's transactions. A factory reset
   is not needed merely to repeat an ordinary connection or tariff save.

The unresolved facts are the installed device's profile, its exact downloaded
tariff and stored schedule, its actual RTC value and synchronization source,
DST handling, firmware activation timing, and physical response to event modes.

## Primary sources

- Supplied iCOMM 14.1.0 APK identified above; recovered function/module references
  are included with each finding.
- PSEG Long Island rate calendar:
  https://www.psegliny.com/TimeOfDay/RateCalculator
- PSEG Long Island Common Residential Rates, printed page 6 (Rate 195):
  https://www.psegliny.com/aboutpseglongisland/ratesandtariffs/-/media/A0FDA80A6FE44A45973922422E86BD9E.ashx
- AO Smith Use & Care Guide 100379654, printed pages 25 and 27:
  https://assets.hotwater.com/damroot/Original/10009/100379654.pdf
- AO Smith service handbook 2000620230, printed page 17:
  https://assets.hotwater.com/damroot/Original/10017/2000620230.pdf
