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
| Utility demand-response pause | Implemented, opt-in | Physical/app flag and restoration check |
| Advanced load-up | Implemented, opt-in | Behavior and readback on actual heater |
| Utility enrollment device flag | Implemented, opt-in | Does not replace utility account enrollment |
| Remaining days and utility status | Implemented optional sensors | Firmware-specific sentinels and availability |
| Hot-water availability | Implemented raw level | Percentage mapping not established |
| Fault status | Raw code and fault-present entity | Model-specific code descriptions |
| Energy use and history | Raw local capture; no kWh entity yet | Word order, scale, counter/instantaneous behavior |
| Actual tank temperature / running components | No confirmed local mapping | Telemetry source and units |
| Utility rate and time-of-use | Serializer/writer paths located; no programming yet | Clock, preference map, checksums and readback |
| On-heater schedules and holidays | Located, not enabled | Complete round-trip/backup/restore before writes |
| Cloud notifications and energy graphs | Use HA automations/history once data exists | No cloud history imported |
| Wi-Fi setup, account sharing and utility signup | Outside local heater-control scope | Require separate network/account workflows |
| Leak accessories, fault reset, temperature differential | App has family-specific/cloud operations | Next-generation model applicability and local mapping |

## Next evidence to collect

1. Inspect extended registers, download diagnostics, and record a contemporaneous
   app energy reading. Repeat across a heating cycle to distinguish counters.
2. Test one-day Vacation then return to the previous mode; compare countdown.
3. Test Guest duration and restore. Test boost only on a model that offers it.
4. Capture/compare an existing time-of-use plan before any schedule programming.

A passing simulated peripheral test checks our encoding and recovery; it does
not prove that an optional feature exists on a particular heater. Contributions
should include model, firmware, redacted captures and expected physical behavior.
Never submit a pairing identifier, PIN, APK, account token or Wi-Fi credentials.
