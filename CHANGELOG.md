# Unreleased — 0.3.2.dev0

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
- This is a development change, not a completed release or hardware-validation claim.

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
