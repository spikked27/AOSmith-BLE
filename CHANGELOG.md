# 2.0.0 — October 5, 2026

- Promote full-schedule savings changes to an everyday control; persist applied
  plan, preference and completion time separately from pending upload data.
- Add compact tariff display and explicit updating/incomplete states.
- Simplify configuration to ZIP, utility, rate and savings preference; synchronize
  local time automatically when applying a new tariff.
- Accept the captured zero-minute clock readback only with a positive ACK and
  matching date/hour; preserve verification scope in diagnostics.
- Auto-detect Hot Water Plus and expose Electric duration alongside Vacation/Guest.
- Remove public restore/word-only trial controls and experimental settings;
  hide diagnostic sensors by default and preserve opted-in diagnostic buttons.
- Preserve pairing, stable entity IDs, original backups and user settings on upgrade.
- Add HACS installation/status badges and improve public documentation and issue forms.

# 1.3.1 — October 5, 2026

- Prevent a failed upload from becoming success on repeated options-flow result
  callbacks. Cache the selected plan only after a confirmed upload result.
- Read back clock/schedule writes after a missing ACK without replaying the write;
  reject empty success ACKs as read data. Retain command traffic and mismatched
  clock words after extended scans for the next hardware trial.
- Send explicit options-menu labels so the three choices remain visible with
  stale or missing frontend translations.
- Tie tariff upload tasks to the config entry and cancel them on unload/shutdown.
  Report cancellation in the options flow, preserve partial-write diagnostics and
  retain the original backup; never automatically replay interrupted writes.
- Move schedule compilation to HA's executor and validate capacity before event
  expansion. Save the actual API input before compilation and log upload phases.
- Add regression coverage for entry unload, HA shutdown during a partial write,
  main-loop task tracking, capacity checks and visible menu labels. 201 tests pass.
- Compare actual Rate 194/195 API inputs with the full original backup: season
  bytes match 195 / More Savings despite the More Hot Water preference word.
  Document all generated preferences and the unresolved zero-minute clock reads.
- The owner-reported HAOS shutdown trigger is not established by the screenshot;
  these fixes address reproduced lifecycle defects without claiming a root cause.

# 1.3.0 — October 5, 2026

- Add diagnostic read status and a persistent finished notification. Continue
  extended scans after optional-register status 0x40 and report rejected/unread counts.
- Move the experimental preference trial to readable 28:75, with a separate backup
  from 28:113 and no automatic address fallback.
- Add the explicit HA-local clock trial with acknowledgement and readback.
- Restore anonymous tariff lookup and preference-dependent schedule generation.
  Save the full original before upload, verify each chunk, and provide read/restore
  controls. Cached-tariff preference changes rebuild the complete schedule.
- Fill all twenty event slots in each season, including the app builder's apparent
  omitted tail; keep actual activation, clock and heating behavior unverified.
- Show running/downloaded integration versions and pending-restart status. Code
  updates still require HA restart; settings/tariff actions do not.
- Pass 187 automated tests plus lint, formatting and release archive checks.

# 1.2.0 — October 5, 2026

- Add opt-in experimental energy-preference dropdown using the app BLE address
  28:113, with a persistent pre-test backup and Restore button.
- Verify the backup on disk before writing; send at most one write and require
  matching readback. No automatic address fallback or write retry.
- Record raw before/after results and distinguish stored-word confirmation from
  unverified heating behavior. Keep schedule/clock programming out of this test.
- Trace preference-dependent schedule generation and repeat the clock review,
  including the legacy profile guard, native DEX tables and battery-backed clock
  evidence. Next-generation clock synchronization remains unresolved.

# 1.1.2 — October 5, 2026

- Add two read-only energy-preference candidates to the existing manual Inspect
  capture, to resolve conflicting next-generation APK register addresses.
- Document the three app preferences, distinct wire/cloud encodings, and the
  before/after capture needed before a writable control can be implemented.
- No new entities, options, automatic reads, or heater-setting writes.

# 1.1.1 — September 29, 2026

- Correct HPS10 hot-water availability to raw 10 = High/100%, 5 = Medium/50%,
  and 0 = Low/0%, as specified by the owner after the new raw 10 capture.
- Update category attributes, captured-frame regression tests and documentation.
- Preserve unknown-code handling, raw diagnostics and existing entity identity.

# 1.1.0 — September 29, 2026

- Fix the shrinking temperature ceiling: use the documented 95–150°F HPS10 range,
  independent of the current setpoint and unverified maximum-register behavior.
- Make Vacation/Guest mode a duration dropdown following the selected mode;
  default Vacation to 7 days and Guest to 1, with Off in other modes.
- Default availability to HPS10 categories and remove calibration configuration.
- Remove retired entity-registry entries automatically; leave current debug
  controls disabled by default without purging recorder history or pairing.
- Add Internet/iCOMM recovery guidance for clock fault 42, with verification.
- Keep tariffs out and explain stale offline schedule/rate limitations.
- Rewrite installation and everyday-use documentation.

# 1.0.0 — September 29, 2026

- One-step Vacation control replaces the draft two-step duration flow.
- Restrict timed Electric to the HPS10 manual’s 1–7 days.
- Remove speculative availability scales, redundant entities and unused options.
- Keep temperature, energy and active countdown reads enabled automatically.
- Default debug buttons off, with one-time upgrade migration; retain pairing/history.
- Preserve the full availability word; no unsupported Low/-5 interpretation.
- Document release scope, installation, upgrades, debugging and hardware limits.
- Publish versioned install archives after automated checks.

# Development history — 0.3.2.dev2

- Add device-page Mode duration for Vacation, Guest and Electric, with explicit
  Until changed options and mode-specific limits. Display the active countdown.
- Keep active countdown reads when optional diagnostics are disabled.
- Reject duration changes when the live mode differs from the UI snapshot.
- Verify duration through the dedicated remaining-days register if a mode read
  returns only its code; a matching mode alone does not confirm duration.
- Keep 20 command outcomes separately from routine traffic, without credentials
  or Bluetooth backend exception text. Never automatically replay a write.
- Confirm in APK bytecode that the discovered clock writer is called only for
  the older heatPump profile. No next-generation clock writer has been established.
- Follow the reported remote temperature limit up to the model's documented
  150°F ceiling; fail conservatively when the maximum is missing and keep reads independent of
  optional diagnostic settings. Explain physical-control maximum adjustment.
- Separate clock requirements for basic control/countdowns versus heater-owned
  schedules. Identify next-generation clock-unset fault 42 and document the
  manual's nine-hour Vacation recovery behavior.
- This is a development change, not a completed release or hardware-validation claim.

- Remove tariff lookup, cached plans, preview entity, HTTP code and options. Clear
  old cached plans on upgrade; retire duplicate entities without deleting history.
- Consolidate faults into Error status, preserving the prior binary sensor ID.
  Include readable descriptions, unknown codes and clock-unset code 42.
- Permit setup while Vacation reports 50°F; release the connection after failed
  initial refresh; hide retained countdown readings outside their active mode.
- Recheck live temperature maximum before writes. Missing/invalid maximum data
  never authorizes a higher setting; polling failures do not show a healthy fault state.
- Pass 129 software tests and Ruff checks. Await remaining availability evidence and
  physical duration checks before calling the development work a final release.
- Add an opt-in HPS10 observed availability mapping: raw 0 → Medium/50%, raw 5 →
  High/100%, all other codes unknown. Preserve raw readings and entity identity;
  document that percentages are category labels and not measured tank volume.
- Add captured-frame and unknown-code tests; 129 local tests pass.

# 0.3.1 — availability calibration and recovery fixes

- Replace the unlabeled raw availability display with a percentage entity and
  per-heater scale selection. Default is unknown until calibrated; retain the
  raw byte and existing entity ID. Five-level mapping is clearly provisional.
- Keep Refresh/Reconnect/Inspect usable when a poll fails.
- Ignore stale BLE callbacks from closed connections, including a reused client object.
- Match the app's Vacation behavior: hide setpoint controls and reject temperature
  writes after checking the live mode. Return useful errors for invalid inputs.
- Add the owner's confirmed grouped energy response as a credential-free fixture.
- Record zero-valued clock-candidate captures as unresolved, not verified.

# 0.3.0 — tariff preview and entity cleanup

- Optional anonymous ZIP/utility/tariff lookup with confirmation, validated cache,
  retained seasons/holidays, explicit replacement/removal, and no background requests.
- Local cumulative energy sensor (kWh); reads all three words in one response.
  Unsupported/malformed reads produce unavailable, never a fabricated zero.
- Retire demand-response controls/status entities; stop routine utility polling.
  Retain old entity history and preserve existing core entity IDs/options.
- Disable duplicate/raw diagnostic sensors by default for new registrations.
- Add timestamped candidate-clock reads to manual inspection and host timezone
  metadata to diagnostics. Clock and schedule writes are not enabled.
- Add tariff flow/error/cache and grouped-energy tests.

# Changelog

## 0.2.0 — 2026-09-29 (development preview)

- Record successful HPS10-80H45DV physical setpoint, reconnect and HA restart tests.
- Enable temperature controls by default; preserve explicit disabled preferences.
- Add Vacation/Guest selections and per-heater timed-mode action.
- Add remaining-days, device maximum/remote setpoint, fault-present and utility sensors.
- Add opt-in Hot Water Plus and utility flag controls from the APK mappings.
- Add bounded read-only extended-register capture to downloadable diagnostics.
- Isolate unsupported optional registers and back off optional transport failures.
- Check the current device mode before boost writes; retain one-write/readback behavior.
- Document complete feature coverage and remaining energy/tariff/schedule research.

## 0.1.1

- Improve discovery scan/wait and retry/manual fallback.
- Add separate temperature-setpoint sensor and explain the native temperature editor.

## 0.1.0

- Initial local BLE pairing, polling, mode control and redacted diagnostics.
