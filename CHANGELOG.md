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
