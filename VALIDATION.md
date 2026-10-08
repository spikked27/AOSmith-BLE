# Version 2.2.0 validation

Reviewed October 7, 2026. Automated checks use Python 3.13.15 and Home Assistant
2025.12.5, the supported minimum series. The owner's installation runs HA 2026.9.4.
**225 tests pass locally**, plus Ruff lint/format and release archive validation.
The GitHub Tests workflow gates publication of the versioned release.

## Software coverage

- Discovery, local pairing/reuse, authentication, serialized Bluetooth requests,
  read recovery, unsupported-register handling and no automatic write replay.
- Temperature bounds, modes, Electric/Vacation/Guest durations, countdown readback,
  mode-change guards, availability categories, faults and cumulative energy.
- Public entity defaults, automatic Hot Water Plus detection, simplified tariff
  setup, no restore entities, stable existing IDs and one-time upgrade migration.
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
The later write is not evidence of autonomous hour rollover. The independent
clock check remains separate from the release.

## Remaining physical validation

Clock ticking, DST, schedule activation/heating effects, countdown expiry and
power-loss persistence are not yet demonstrated by the supplied captures.
Additional models, active proxies, Hot Water Plus effects, pairing-slot limits,
long idle/recovery and energy-counter resets require further physical testing.
Storage/readback success does not establish these effects.

Version 2.2.0 removes automatic clock maintenance and the tariff upload's clock
write. Regression tests require no clock reads/writes from startup, fault handling,
recovery or normal polling, no block-26 writes during tariff upload, and exactly
one explicit manual clock write with durable operation history. Migration restores
only manual clock buttons disabled by the integration, preserving user choices.

DR tests exercise the full block-27 read allowlist, per-register timestamps,
unsupported-word continuation, transport failure with partial capture retention,
no register writes or enrollment, bounded history/diffs, session deadlines,
repeated-start rejection, cancellation, interrupted restart, and targeted actions.
The fake peripheral validates transport and lifecycle logic; the new unknown
status words still need physical captures to identify an active DR mapping.

New Python code requires a Core restart; normal options and tariff changes do not.
The read-only monitor is opt-in, stops at its deadline/unload/restart, and does not
resume itself. Captures are deliberately labeled raw rather than live DR levels.

The reported HAOS shutdown screenshot shows services stopping and Supervisor
waiting, not its initiating cause. No host shutdown was reproduced or invoked by
this integration. Corrected upload lifecycle defects are covered by tests without
claiming they caused that shutdown.
