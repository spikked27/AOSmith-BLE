# Version 1.0.0 validation

Reviewed September 29, 2026. Local environment: Python 3.13.15 and Home Assistant
2025.12.5 with its Bluetooth/USB dependencies. **145 automated tests pass locally**, with Ruff lint and formatting checks passing.
Automated checks use captured
protocol fixtures and a simulated peripheral, not physical Bluetooth. See the
GitHub Tests workflow for the release commit's results.

## Software coverage

- Discovery by name/service, shared HA scan, manual fallback, per-device setup,
  identifier validation and reuse without duplicate enrollment.
- Serialized requests, read recovery, stale-notification rejection, failed-setup
  and unload cleanup, and no automatic write replay.
- One-step Vacation selection from every supported mode, duration bounds,
  indefinite sentinel, Off-to-Hybrid, stale-mode guard and device countdown
  readback. A targeted mode/days action supports Guest and Electric as well.
- Temperature editor and writes respect Vacation mode and live remote limits
  through 150°F. An unknown maximum cannot authorize an increase.
- Error status includes clock code 42, keeps unknown faults explicit and becomes
  unavailable after failed polls.
- Grouped 48-bit energy reads, optional-read backoff and unknown data handling;
  captured HPS10 High/Medium frames; unsupported availability codes remain unknown.
- Five default entities; three disabled debug buttons; one-time debug migration
  that allows later user opt-in; old options and duplicate entities retired
  without changing pairing credentials or deleting history.
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
- Nearby app/cloud observations support raw 5 = High/100% and raw 0 = Medium/50%.
  These were not atomic simultaneous captures; Low's BLE code remains unknown.

## Release limitations

Finite Vacation/Guest/Electric countdowns, expiry and recovery are software-tested
but not physically validated. The one-step Vacation UI and migration are new in
this release. The manual describes nine hours of Vacation recovery; Electric is
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
