# Version 3.0.0 validation

Reviewed October 7, 2026. Automated checks use Python 3.13.15 and Home Assistant
2025.12.5, the supported minimum series. The owner's installation runs HA 2026.9.4.
**281 tests pass locally**, plus Ruff lint/format and release archive validation.
The GitHub Tests workflow gates publication of the versioned release.

## Software coverage

- Discovery, local pairing/reuse, authentication, serialized Bluetooth requests,
  read recovery, unsupported-register handling and no automatic write replay.
- Temperature bounds, modes, Electric/Vacation/Guest durations, countdown readback,
  mode-change guards, availability categories, faults and cumulative energy.
- Public entity defaults, removal of diagnostic entities, automatic Hot Water Plus
  detection, stable normal-control IDs, legacy availability compatibility and migration.
- Durable original backups, full five-season/holiday/preference uploads, 60 fresh
  readback confirmations, all twenty event slots and stopping after write errors.
- All three preference schedules compared with independently recovered fixtures.
- Applied tariff/preference survives coordinator restart without an options-flow
  save. A failed update preserves the last confirmed metadata and exposes an
  incomplete status until a subsequent complete upload succeeds.
- Concurrent tariff requests rejected. Caller cancellation does not cancel a
  preference upload; entry unload does. HA shutdown cancels a partially sent write,
  releases locks and preserves the original backup and interrupted phase.
- Main-loop-safe schedule compilation and entry-owned background tasks. Options
  progress reports success only after a confirmed result, including repeated callbacks.
- Clock packet encoding and captured zero-minute reply replay. Acknowledged partial
  readback requires matching date/hour and a zero minute byte; incorrect date/hour,
  a different nonzero minute, or a missing ACK does not satisfy this exception.
  Diagnostics retain the actual words, command traffic and verification scope.
- Diagnostic completion notifications, raw unsupported results, redaction,
  running/downloaded versions, translations, service schema and release packaging.

One upstream aiohttp/Home Assistant deprecation warning remains in the minimum
version environment. Automated tests simulate the peripheral; they do not replace
physical Bluetooth tests.

## Hardware evidence

The tested heater is HPS10-80H45DV, reported firmware 6.4. Owner captures establish
local authentication/readings, basic mode changes, a sustained HA connection,
availability raw 0/5/10, and tariff lookup from the owner's HA installation.

A v1.3.1 Rate **194 / More Hot Water** upload completed all 60 chunks. An independent
read after integration reload matched **all 678 stored bytes**: five 124-byte season
blocks and 29 extra words. The original backup remained unchanged. The saved
original season bytes match Rate **195 / More Savings**, despite its separate
preference word having been changed to More Hot Water during an earlier test.
This is why v2 always rebuilds the entire schedule for preference changes.

The 20:51 EDT clock trial sent `3314 3545` and received a valid positive ACK;
readback returned `0014 3545`. The later 21:00 trial wrote and read `0015 3545`.
Version 2 accepts the first observed shape as acknowledged date/hour readback,
while retaining `minute_verified: false` and `rtc_running_verified: false`.
The later write is not evidence of autonomous hour rollover. Version 3 verifies
timing independently through DR transitions; it never compares those clock fields
to host time to infer drift.

## October 7 DR capture and replay

The owner's v2.2.0 capture contains 75 complete snapshots between approximately
20:51 and 22:05 EDT, without register-read errors. Register 27:0 stayed `0600`
through 21:59:59.421, then was `0000` at 22:00:59.365. The applied Rate 195 / More
Savings schedule changes DR1 to Baseline at 22:00. This supports the high-byte DR
mapping and a working tariff transition despite 26:3–4 retaining the earlier
written hour. DR2/DR3/Load up mappings follow the app's schedule event codes and
need equivalent live captures.

The redacted fixture in `tests/fixtures/dr_transition_20261007.json` includes the
75 DR timestamps/values, availability codes and schedule bytes only. The replay
observes an on-time transition and issues no clock writes. Version 2.2 did not
capture historical mode in each row; replay supplies Hybrid from the final state,
so continuous Hybrid operation remains an assumption. Version 3 captures mode,
setpoint and fault in future diagnostic snapshots.

Availability register 27:23 returned raw zero throughout that observation window.
This establishes a heater-reported value, not a stuck HA percentage conversion.
Raw zero is the Low category; it does not establish zero usable gallons. A stuck
heater estimate versus a genuinely low level needs comparison with iCOMM and
actual hot-water delivery. No measured tank temperature is exposed.

## Clock verification tests

Automated tests cover value-changing boundaries, weekday/weekend schedules,
overnight carry, season/year wrap, holiday/observed-date pauses, DST pauses and
unknown DR codes. Simulated misses require pre-boundary evidence, three minutes
of grace and three fresh mismatches spanning at least one minute.

Correction tests verify complete matching schedule bytes, a fresh pre-write status
check, no write after an override/timezone/deadline change, durable limits before
transmission, no repeat after restart/failure/cancellation, a 24-hour cap even after
resolution, and a later on-time transition before clearing the active desync.
One test exercises the actual clock wire writer against a simulated peripheral.
Malformed tariffs leave core readings available. Unsupported/missing reads and
Electric/Vacation/Guest/Heat pump modes cannot trigger correction. Legacy applied
plans are reconstructed separately from an unconfirmed upload candidate.

Startup, ordinary recovery and tariff application remain write-free by themselves.
The clock switch and explicit manual button are tested. A desync label represents
missed schedule execution; the tests do not prove a physical clock fault.

## Remaining physical validation

Automatic repair effectiveness, long-term clock accuracy, DST recovery, tariff
heating effects, timed-mode expiry and power-loss persistence need further live
validation. Other models, active proxies, Hot Water Plus effects, pairing-slot
limits and energy-counter resets are also unverified. A release passing automated
tests does not establish those physical behaviors.

DR tests cover the fixed read allowlist, timestamps, unsupported-word continuation,
partial captures, no writes/enrollment from diagnostic actions, bounded history,
session deadlines, cancellation/restart and targeting. New code requires a Core
restart; pairing and stored tariffs are preserved. Diagnostic entities are removed
on upgrade while their evidence and corresponding read-only actions remain.

The reported HAOS shutdown screenshot shows services stopping and Supervisor
waiting, not its initiating cause. No host shutdown was reproduced or invoked by
this integration. Corrected upload lifecycle defects are covered by tests without
claiming they caused that shutdown.
