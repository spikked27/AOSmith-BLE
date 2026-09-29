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
