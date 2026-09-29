# Validation of unreleased development 0.3.2.dev1

September 29, 2026. Python 3.13.15 and Home Assistant 2025.12.5 with its
Bluetooth/USB dependencies. **115 automated tests pass**, with Ruff lint and
formatting checks passing. One upstream aiohttp/Home Assistant deprecation
warning remains. Tests use a simulated peripheral, not physical Bluetooth.

## Review performed

| Area | Review and validation |
|---|---|
| Pairing/discovery | Name/service matching, shared HA scan, manual fallback, identifier validation, reuse without duplicate enrollment; setup now accepts Vacation's 50°F reading |
| Connection lifecycle | Serialized requests, reconnect/read retry, old notification rejection, disconnect after failed setup, unload cleanup; no automatic write replay |
| Modes and durations | Device-page control and targeted action, mode-specific sentinels, live stale-mode rejection, dedicated countdown confirmation when needed; inactive countdown sensors no longer imply active timers |
| Temperature | Reported limits through 150°F, fresh maximum check before writes, missing/invalid maximum cannot permit an increase; live Vacation write guard |
| Faults | One Error status binary sensor, low-byte descriptions and raw word, fault 42 clock-not-set, unknown faults retained, unavailable after failed polls |
| Tariff removal | No HTTP lookup, UI steps, preview or cached plan; upgrade clears obsolete options and retires owned tariff/raw-fault entities without deleting history |
| Telemetry | Grouped 48-bit energy read, unavailable/error values do not become zero, optional reads back off without dropping core readings; availability conversion remains explicitly unverified |
| Diagnostics/privacy | Pairing material omitted, ordinary traffic bounded, command outcomes retained separately, backend exceptions redacted in command history; removed tariff cache excluded |
| Packaging | Manifest/version, HACS layout, English strings, action schema, docs and test workflow reviewed |

The reduced suite no longer tests the deleted tariff lookup; its upgrade/removal
coverage replaces those obsolete tests. A passing simulated test proves software
behavior, not model capability or successful physical operation.

## Owner-confirmed hardware results

Model HPS10-80H45DV, reported firmware 6.4:

- Authentication, register reads and Hybrid → Heat Pump → Hybrid using nRF Connect.
- At least 30 minutes of continuous HA connection with working controls/status.
- Setpoint 125 → 124 → 125°F, checked against the physical display.
- Reconnect and HA restart without pressing the heater Bluetooth button again.
- Grouped three-word energy request/reply: 350.532 kWh, matching the app's ~350 kWh.
- Four zero-valued older-profile clock-candidate captures; these do not validate
  a running clock, a clock setting method or a timezone. No repeat requested.

## Remaining release acceptance

1. **Availability:** diagnostics during normal shower use, paired with the app's
   visible bars/category/percentage and approximate time. Ideally capture a
   changed indication and recovery. No extra water use is needed. Official cloud
   LOW/MEDIUM/HIGH → 0/50/100 does not establish BLE raw 5's meaning.
2. **Duration UI:** one consolidated check of Vacation 7 days → Until changed →
   previous mode; Guest 2 days → previous mode; Electric 2 days → previous mode.
   Compare the physical/app countdown and download diagnostics afterward. These
   controls are software-tested, not yet physically validated in this build.
3. **Upgrade:** verify the old tariff entity is disabled, the cache is removed,
   one Error status indicator remains, and existing pairing/controls still work.

Do not claim completion of finite-day expiry or power-loss behavior from a
successful command alone. The HPS10 manual describes nine hours of Vacation
recovery and Electric durations of 1–7 days; the generic APK's longer Electric
options are not confirmed for this heater.

Additional-model support, active Bluetooth proxies, pairing-slot limits,
long radio idle/power recovery, energy-counter reset behavior, Hot Water Plus
(on models that offer it), and internet-blocked endurance remain unverified.
Generic setup does not mean universal support for every iCOMM family.

Clock synchronization is not required by the implemented control/countdown
commands. Fault 42 can report an unset clock; no fault does not establish clock
accuracy. Utility configuration remains in the official app. This integration
makes no guarantee about heater-owned offline TOU schedules.

These changes stay in the development draft PR. Main remains 0.3.1; no final
release or tag is created before the outstanding evidence is reviewed.
