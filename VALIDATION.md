# Validation of unreleased development 0.3.2.dev0

September 29, 2026. Python 3.13.15 and Home Assistant 2025.12.5 with its
Bluetooth/USB dependencies. Ruff lint and formatting checks pass.

109 automated tests cover captured read packets, exact APK CRC, temperature and
timed-mode encoding, synthetic HMAC, framing, authentication/recovery, serialized
requests, write/readback and uncertain writes without replay. New coverage checks
optional-register rejection, timeout/backoff without losing core readings, manual
read-only inspection retry, boost's live mode prerequisite, per-heater timed action
targeting, optional-entity availability, exact A5 switch encoding, feature options,
and service UI selectors on the minimum supported HA test runtime. Version 0.3.0
adds grouped energy reads, invalid/unsupported energy without fabricated zeros,
tariff HTTP/GraphQL error handling, season/holiday preservation, settings/cache
isolation, offline preview, and scoped retirement of legacy utility entities. Version 0.3.1 adds explicit
availability-scale boundaries, raw-value retention, the captured grouped-energy
reply, offline recovery-button use, obsolete notification rejection and live
Vacation-mode temperature-write prevention.

The unreleased change adds device-page duration boundaries/sentinels, stale
mode rejection before writes, separate mode/countdown confirmation, active
countdown polling without diagnostic reads, persistent-in-session command
outcomes, and backend-error redaction. The test peripheral exercises both
full-word and split mode/countdown readback. Neither simulation constitutes a
physical duration test.

One upstream aiohttp/Home Assistant deprecation warning remains during import.
The tests do not connect to physical BLE hardware.

## Owner-confirmed hardware results

Model HPS10-80H45DV, reported firmware 6.4:

- Authentication, register reads and Hybrid → Heat Pump → Hybrid using nRF Connect.
- 30-minute continuous HA connection with working controls and temperature status.
- HA setpoint 125 → 124 → 125°F, checked against the heater's physical display.
- Reconnect Bluetooth action without pressing the heater Bluetooth button.
- Automatic reconnection after Home Assistant restart without pressing that button.
- 0.3.0 grouped three-word energy request/reply: 350.532 kWh.
- Anonymous PSEG 195 tariff selection persisted with all ten events and holidays.
- Two successful clock-candidate captures about four minutes apart both read zero;
  they do not validate clock mapping or synchronization.

## Still to validate

Version 0.2.0 timed modes, remaining days, utility registers, and Hot Water Plus
(on supported models) are APK-derived and have not yet been hardware tested.
The local 350.532 kWh interpretation matches the owner’s approximately 350 kWh
app value. Grouped reads are now hardware confirmed; heating-cycle deltas and reset
behavior still need testing. Tariff lookup/cache is implemented; clock synchronization and
on-heater schedule programming remain unimplemented pending validation.
Discovery retest, additional adapters/proxies/models, multi-slot pairing, long
radio idle or heater power interruption, and internet-blocked endurance remain
open. Passing these tests is not a claim of universal iCOMM compatibility.


## Release acceptance still outstanding

The duration UI is software tested but not yet installed or tested on the owner's
heater. One consolidated hardware pass should check Vacation 7 days → Until
changed → previous mode, Guest 2 days → previous mode, and Electric 2 days →
previous mode. Compare the heater/app countdown with HA and download diagnostics
once afterward. Command outcomes now survive polling. Do not repeat clock reads
that already returned zero four times.

A core-control release does not require clock synchronization. Full on-heater
offline scheduling remains blocked by clock behavior and schedule serialization/
verification; availability category mapping also remains unresolved. Native finite-day countdown expiry, loss-of-power behavior, optional
boost and additional models are also not established. No release/tag was made
for these development changes; the main branch remains the published 0.3.1.


Temperature research adds tested UI bounds at reported 125, 140 and 150°F,
unknown/invalid maximum fallback, and maximum-register polling independent of
diagnostic options. These tests do not raise the physical heater's temperature.
The hard ceiling is now 150°F, supported by the model manual, while a lower
reported remote limit is still honored. All 109 local tests and Ruff checks pass.
