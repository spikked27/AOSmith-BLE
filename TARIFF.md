# Tariff and offline-clock readiness

## Implemented in 0.3.0

The optional lookup follows iCOMM 14.1.0's anonymous GraphQL queries at
`https://r2.wh8.co/graphql`, with `brand: icomm` and `version: 14.1.0`.
No account, bearer token or extracted application secret is used. The service
is not a documented public API and may change. It is called only from options
setup. Network errors preserve the previous cache and do not affect BLE control.

Selection stores utility/tariff IDs, labels, retrieval time, every seasonal event
and holiday ID/name in HA config-entry options. ZIP is not retained. The cache
is included in normal HA backups and diagnostics; no pairing material is added.
Selecting, replacing or removing a plan makes no heater-setting write.

PSEG Long Island residential 195 was found as utility 200, tariff 3439409.
Its returned plan has June 1 / October 1 seasons, weekday peak 15:00–19:00,
daily lowest-price hours 22:00–06:00, remaining off-peak hours, and ten holiday
entries. This is the API's plan, not a guarantee of the current utility bill.
The API also lists a separate power-supply-only 195 tariff; these are not interchangeable.
The cache is a preview, not a live price sensor or billing calculation.

## How offline time will work

The intended design is for Home Assistant to supply local date/time over BLE.
HA uses its configured IANA timezone (for example America/New_York) to handle
daylight-saving rules. The heater need not contact an Internet time server.
HA still needs an accurate system clock, supplied by its host/RTC or time service.

The APK contains a clock writer for block 26, words 3–4. It builds local
minute/hour plus a packed year/month/day, rather than sending an IANA timezone.
That mapping is defined alongside older-heater registers, so its applicability
to the next-generation profile is unverified. Manual Inspect reads these two
candidate words only; there are no clock writes in this version.

Once validated, synchronize after connection/power recovery, check drift
periodically, and handle HA timezone/UTC-offset changes. Readback must establish
whether firmware already adjusts DST to avoid applying it twice. Check invalid
host time and invalid/reset heater time before enabling any on-heater schedule.
Do not assume the heater retains date/time after loss of power, or that it keeps
advertising after a reboot. Those are hardware tests, not software guarantees.

## Remaining gates before Apply tariff

| Area | Required evidence / behavior |
|---|---|
| Device clock | Two timestamped captures showing minute/date progression; correct profile map; write/readback, power-loss and DST tests |
| Seasons | Full-year wrap, exact start dates, leap day, supported season/event capacities |
| Weekdays/holidays | Day-bit mapping, fixed versus observed dates, nth/last weekday rules, unknown holiday rejection |
| Preferences | Confirm comfort/savings mapping, shed command meaning and preheat timing; these differ from operation modes |
| Serialization | Validate event padding, final checksum word and next-generation holiday/preference offsets |
| Existing schedule | Read complete schedule first; persist a backup and offer deliberate restore |
| Interrupted write | Serialize all operations; stop on disconnect, never replay mutations automatically; identify partial application and verify every changed block |
| Activation | Readback must distinguish saved, active and overridden schedules; do not label a cache as applied |
| HA unavailable | Establish heater-owned schedule behavior, last manual setting, and recovery without relying on HA always running |
| Other models | Explicit supported register profiles/capabilities; an ICOMM name is not sufficient |

The APK's BLE and Wi-Fi holiday writers appear to use inconsistent preference
offsets for newer heaters. That must be resolved with actual next-generation
readback; the older layout must not be copied blindly.

## Next physical checks

1. Confirm the new Energy usage value against iCOMM; repeat after a heating cycle.
2. Press Inspect extended registers, download diagnostics, wait at least two
   minutes, and repeat. Note the heater's displayed time/date if it exposes them.
   Host UTC and configured timezone are recorded; candidate clock words are raw.
3. Confirm selecting a tariff displays the expected utility and tariff with ten
   events/ten holidays for the observed PSEG 195 response. Heater mode/setpoint
   should remain unchanged by tariff selection.

No intentional power interruption is needed for these first checks. Schedule
programming, clock synchronization, price-based control and cost calculation
remain unimplemented until the relevant evidence is available. Demand-response
enrollment/control remains out of scope.


## Hardware capture result — September 28, 2026

Two captures approximately four minutes apart returned zero for both clock
candidate words with successful ACKs. That does not establish a running clock:
these could be unset values or an inapplicable register map. Clock writes remain
unimplemented; repeated reads of the same two zero words are not a validation
plan. The next step is to identify the next-generation clock source and format.
The saved PSEG 195 cache and the grouped 350.532 kWh read were present and valid.
