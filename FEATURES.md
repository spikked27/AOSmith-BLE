# iCOMM feature coverage

This inventory concerns next-generation heat pumps. iCOMM also supports older
heat pumps, electric, gas, tankless and recirculation products with other maps.
“Generic” means reusable setup and per-device state, not universal protocol support.

| App function | Integration status | Remaining evidence |
|---|---|---|
| Local pairing and reconnect | Implemented; hardware tested | Additional models, proxy and pairing-slot tests |
| Temperature and Electric/Hybrid/Heat Pump | Implemented; hardware tested | Wider model coverage |
| Vacation/Guest/timed Electric | Implemented; APK-derived | Physical display and remaining-days checks |
| Hot Water Plus 0–3 | Implemented, opt-in BEST profile feature | Supported heater and mode interaction check |
| Utility demand-response pause | Removed from product scope | Raw read-only research capture remains |
| Advanced load-up flag | Removed from product scope | Separate from future tariff preheating |
| Utility enrollment device flag | Removed from product scope | No account enrollment |
| Remaining days | Optional diagnostic sensors | Firmware-specific sentinels and availability |
| Hot-water availability | Implemented raw level | Percentage mapping not established |
| Fault status | Raw code and fault-present entity | Model-specific code descriptions |
| Energy use and history | Local cumulative kWh sensor | Heating-cycle delta, reset behavior and other models |
| Actual tank temperature / running components | No confirmed local mapping | Telemetry source and units |
| Utility tariff lookup | Anonymous lookup and cached seasonal/holiday preview | Optional remote API may change; no heater programming yet |
| On-heater schedules and holidays | Located, not enabled | Complete round-trip/backup/restore before writes |
| Cloud notifications and energy graphs | Use HA automations/history once data exists | No cloud history imported |
| Wi-Fi setup, account sharing and utility signup | Outside local heater-control scope | Require separate network/account workflows |
| Leak accessories, fault reset, temperature differential | App has family-specific/cloud operations | Next-generation model applicability and local mapping |

## Next evidence to collect

1. Confirm the energy entity tracks the app across a heating cycle. Inspect twice
   at least two minutes apart for timestamped candidate clock values.
2. Test one-day Vacation then return to the previous mode; compare countdown.
3. Test Guest duration and restore. Test boost only on a model that offers it.
4. Capture/compare an existing time-of-use plan before any schedule programming.

A passing simulated peripheral test checks our encoding and recovery; it does
not prove that an optional feature exists on a particular heater. Contributions
should include model, firmware, redacted captures and expected physical behavior.
Never submit a pairing identifier, PIN, APK, account token or Wi-Fi credentials.
