# Version 1.1.2 validation

Reviewed October 5, 2026. Local environment: Python 3.13.15 and Home Assistant
2025.12.5 with its Bluetooth/USB dependencies. **149 automated tests pass locally**, with Ruff lint and formatting checks passing.
Automated checks use captured
protocol fixtures and a simulated peripheral, not physical Bluetooth. See the
GitHub Tests workflow for the release commit's results.

## Software coverage

- Discovery by name/service, shared HA scan, manual fallback, per-device setup,
  identifier validation and reuse without duplicate enrollment.
- Serialized requests, read recovery, stale-notification rejection, failed-setup
  and unload cleanup, and no automatic write replay.
- Mode-aware Vacation/Guest duration selection, duration bounds,
  Vacation 7-day/Guest 1-day defaults, indefinite sentinel, Off-to-Hybrid, stale-mode guard and device countdown
  readback. A targeted mode/days action supports Guest and Electric as well.
- Temperature editor and writes respect Vacation mode and the documented
  95–150°F range. Regression tests lower 125→124, then raise to 125/140/150
  with missing, invalid or setpoint-mirroring maximum-register values.
- Error status includes clock code 42, keeps unknown faults explicit and becomes
  unavailable after failed polls.
- Grouped 48-bit energy reads, optional-read backoff and unknown data handling;
  captured HPS10 raw 0/5/10 frames; unsupported availability codes remain unknown.
- Five default entities; three disabled debug buttons; one-time debug migration
  that allows later user opt-in; old options cleared and retired registry entries removed
  without changing pairing credentials or purging recorder history.
- Redacted diagnostics with bounded event/command histories and full availability
  word preservation, including hypothetical signed -5 representations.
- Manifest, HACS layout, English strings, action schema and release packaging.

Ruff lint/format and pytest must pass before release. One upstream aiohttp/Home
Assistant deprecation warning is present in the minimum-version environment.

## Owner-confirmed hardware behavior

On HPS10-80H45DV, reported firmware 6.4:

- Authentication, register reads and Hybrid → Heat pump → Hybrid.
- At least 30 minutes of continuous HA connection with working controls/status.
- Setpoint 125 → 124 → 125°F checked against the physical display.
- Reconnect and HA restart without reactivating the heater's Bluetooth.
- Grouped energy reading 350.532 kWh agreed with the app's approximately 350 kWh;
  later captures progressed to 350.646 kWh.
- A later capture contains raw 10 twice with valid checksums and no fault.
  The owner directed the corrected 0/5/10 → 0/50/100 mapping. Earlier nearby
  screenshots were not simultaneous and no longer establish the previous mapping.
  The byte values are captured; the revised category interpretation is owner-specified.

## Release limitations

Finite Vacation/Guest/Electric countdowns, expiry and recovery are software-tested
but not physically validated. The revised Vacation/Guest UI and temperature ceiling fix are new in
this release. Temperature increases above 125°F still need hardware confirmation. The manual describes nine hours of Vacation recovery; Electric is
limited to its documented 1–7 days. No claimed exact return time or power-loss
countdown persistence is inferred from the command encoding.

Additional models, active Bluetooth proxies, pairing-slot limits, long radio
idle/power recovery, energy-counter reset behavior, Hot Water Plus and
internet-blocked endurance remain unverified. Generic setup does not imply support
for every iCOMM family.

No verified next-generation clock writer is exposed. Clock fault 42 reports an
unset clock, not its accuracy or timezone. Utility setup remains in the official
app, and heater-owned offline TOU timing is not guaranteed. Repeated zero clock
candidate reads have not established their meaning; no repeat is requested.


Energy-preference capture tests preserve raw 0/1/2/65535, report unsupported
candidates without inventing zero, retry on manual inspection, leave core
readings usable, and issue no register writes. Physical identification and
preference-only activation remain pending; no writable select is exposed.
