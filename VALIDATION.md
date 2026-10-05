# Version 1.3.0 validation

Reviewed October 5, 2026. Local environment: Python 3.13.15 and Home Assistant
2025.12.5 with its Bluetooth/USB dependencies. **187 automated tests pass locally**, with Ruff lint and formatting checks passing.
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
- Nine default entities; four disabled debug buttons; one-time debug migration
  that allows later user opt-in; old options cleared and retired registry entries removed
  without changing pairing credentials or purging recorder history.
- Redacted diagnostics with bounded event/command histories and full availability
  word preservation, including hypothetical signed -5 representations.
- Manifest, HACS layout, English strings, action schema and release packaging.
- Recovered clock encoding, HA timezone selection, acknowledgement/readback,
  initial-read rejection, and no repeated write after rejection or disconnection.
- Anonymous tariff queries with fixtures; all three preference-generated schedules,
  known holiday encoding and rejection of malformed data/unknown holiday IDs.
- Complete five-season/extra-data capture, backup before any mutation, all twenty
  event slots, 60 confirmed schedule chunks, restoration, and stopping on partial
  or mismatched writes. First original backup survives coordinator restart.
- Options-flow upload progress, success/failure handling, caching after confirmed
  upload, diagnostic completion notifications and running/downloaded versions.

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
- The October 5 23:18:56 UTC dump reads 28:75 as `0000`; 28:113 returns status
  0x40. Both read transactions have valid CRCs. Its extended scan stopped at the
  rejection and never reached the clock candidates. The dump predates the owner's
  failed preference-selection screenshot and does not contain that attempted write.

## Release limitations

Finite Vacation/Guest/Electric countdowns, expiry and recovery are software-tested
but not physically validated. Temperature increases above 125°F still need hardware confirmation. The manual describes nine hours of Vacation recovery; Electric is
limited to its documented 1–7 days. No claimed exact return time or power-loss
countdown persistence is inferred from the command encoding.

Additional models, active Bluetooth proxies, pairing-slot limits, long radio
idle/power recovery, energy-counter reset behavior, Hot Water Plus and
internet-blocked endurance remain unverified. Generic setup does not imply support
for every iCOMM family.

The explicit clock trial uses the app's known legacy-profile format at 26:3–4;
its next-generation acceptance, continued ticking, timezone/DST behavior and
power-loss persistence are unverified. Clock fault 42 reports an unset clock,
not its accuracy. The app trace found no next-generation replacement clock setter.
The owner's authorization permits this specific trial without claiming the map
has been proven. No clock write occurs during startup or normal polling.


Energy-preference capture tests preserve raw 0/1/2/65535, report unsupported
candidates without inventing zero, retry on manual inspection, leave core
readings usable, and issue no register writes. Physical identification and
preference-only activation remain pending. Version 1.3.0 changes the opt-in word
trial to the readable 28:75 candidate; its backup is separate from the old 28:113
backup. With a cached tariff the preference rebuilds the full schedule.


New tests cover the three preference wire values, correct destination bytes,
backup-before-write ordering, storage failure preventing writes, unreadable and
unexpected words, no alternate-register fallback, same-value no-ops, ambiguous
and mismatched writes never being repeated, opt-in controls, and backup/restore
across coordinator restarts. Ruff lint/format checks pass. These are simulated
peripheral and Home Assistant tests, not a physical HPS10 test.

Tariff uploads and restores have not been tested on the physical heater. Every
written chunk requires an ACK and matching readback; this is not proof of firmware
activation or physical heating behavior. The writer fills all twenty event slots,
including the two slots apparently omitted by the app's BLE frame builder. The
end-of-season parameter-62 read is retained without inventing its commit semantics.
The restored API was unreachable from this workspace; live lookup must run from
HA. The user runs HA 2026.9.4; automated tests use the supported minimum version.

Integration Reload retains imported modules. No unsupported module-purging hot
reload is implemented. HACS Python updates still need an HA restart; the version
sensor exposes a downloaded/running mismatch after the next poll.
