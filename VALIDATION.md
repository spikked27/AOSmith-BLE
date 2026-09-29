# Validation of development preview 0.3.0

September 29, 2026. Python 3.13.15 and Home Assistant 2025.12.5 with its
Bluetooth/USB dependencies. Ruff lint and formatting checks pass.

63 automated tests cover captured read packets, exact APK CRC, temperature and
timed-mode encoding, synthetic HMAC, framing, authentication/recovery, serialized
requests, write/readback and uncertain writes without replay. New coverage checks
optional-register rejection, timeout/backoff without losing core readings, manual
read-only inspection retry, boost's live mode prerequisite, per-heater timed action
targeting, optional-entity availability, exact A5 switch encoding, feature options,
and service UI selectors on the minimum supported HA test runtime. Version 0.3.0
adds grouped energy reads, invalid/unsupported energy without fabricated zeros,
tariff HTTP/GraphQL error handling, season/holiday preservation, settings/cache
isolation, offline preview, and scoped retirement of legacy utility entities.

One upstream aiohttp/Home Assistant deprecation warning remains during import.
The tests do not connect to physical BLE hardware.

## Owner-confirmed hardware results

Model HPS10-80H45DV, reported firmware 6.4:

- Authentication, register reads and Hybrid → Heat Pump → Hybrid using nRF Connect.
- 30-minute continuous HA connection with working controls and temperature status.
- HA setpoint 125 → 124 → 125°F, checked against the heater's physical display.
- Reconnect Bluetooth action without pressing the heater Bluetooth button.
- Automatic reconnection after Home Assistant restart without pressing that button.

## Still to validate

Version 0.2.0 timed modes, remaining days, utility registers, and Hot Water Plus
(on supported models) are APK-derived and have not yet been hardware tested.
The local 350.532 kWh interpretation matches the owner’s approximately 350 kWh
app value. Grouped reads, heating-cycle deltas and reset behavior still need
hardware testing. Tariff lookup/cache is implemented; clock synchronization and
on-heater schedule programming remain unimplemented pending validation.
Discovery retest, additional adapters/proxies/models, multi-slot pairing, long
radio idle or heater power interruption, and internet-blocked endurance remain
open. Passing these tests is not a claim of universal iCOMM compatibility.
