# iCOMM feature coverage

This inventory concerns next-generation heat pumps. iCOMM also supports older
heat pumps, electric, gas, tankless and recirculation products with other maps.
“Generic” means reusable setup and per-device state, not universal protocol support.

| App function | Integration status | Remaining evidence |
|---|---|---|
| Local pairing and reconnect | Implemented; hardware tested | Additional models, proxy and pairing-slot tests |
| Temperature and Electric/Hybrid/Heat Pump | Implemented; hardware tested | Wider model coverage |
| Vacation/Guest/timed Electric | Mode-aware Vacation/Guest duration control and mode/days action; APK-derived | Physical display and remaining-days checks |
| Hot Water Plus 0–3 | Implemented, opt-in BEST profile feature | Supported heater and mode interaction check |
| Utility demand-response pause | Removed from product scope | Raw read-only research capture remains |
| Advanced load-up flag | Removed from product scope | No utility writes exposed |
| Utility enrollment device flag | Removed from product scope | No account enrollment |
| Remaining days | Vacation/Guest control reads active countdown; other timed modes available through action | Firmware-specific sentinels and expiry |
| Hot-water availability | Default HPS10 observed categories: raw 0 → 0%, raw 5 → 50%, raw 10 → 100%; raw attribute retained | Further paired observations and other models |
| Fault status | One Error status problem entity with readable current fault, including clock code 42 | Additional model/firmware validation |
| Energy use and history | Local cumulative kWh sensor | Heating-cycle delta, reset behavior and other models |
| Actual tank temperature / running components | No confirmed local mapping | Telemetry source and units |
| Utility tariff lookup | Anonymous AO Smith API: ZIP → utility → plan; cached normalized price events | Live API response from owner's HA; no automatic refresh |
| Device clock and timezone | Explicit experimental clock button uses HA's local timezone and recovered 26:3–4 format | Next-gen acceptance, ticking, DST and persistence remain unverified |
| On-heater schedules and holidays | Experimental five-season generation/upload, full read, durable original backup and restore | Physical readback and actual activation/behavior |
| Diagnostic completion | Read-status sensor and persistent finished notification, including rejected/unread counts | Read errors remain visible rather than fabricated data |
| Update visibility | Running/downloaded version and restart-required attributes | Python updates still require HA restart; no host reboot |
| Cloud notifications and energy graphs | Use HA automations/history once data exists | No cloud history imported |
| Wi-Fi setup, account sharing and utility signup | Outside local heater-control scope | Require separate network/account workflows |
| Leak accessories, fault reset, temperature differential | App has family-specific/cloud operations | Next-generation model applicability and local mapping |

## Next evidence to collect

1. Confirm the energy entity tracks the app across a heating cycle. Repeated zero
   clock captures have already been collected; repeating those is not a next step.
2. Test one-day Vacation then return to the previous mode; compare countdown.
3. Test Guest duration and restore. Test boost only on a model that offers it.
4. During normal use/recovery, note any new availability code and matching app
   category. The HPS10 mapping now includes Low/Medium/High; report any contradictions.

A passing simulated peripheral test checks our encoding and recovery; it does
not prove that an optional feature exists on a particular heater. Contributions
should include model, firmware, redacted captures and expected physical behavior.
Never submit a pairing identifier, PIN, APK, account token or Wi-Fi credentials.

Energy usage preference has an opt-in dropdown. With a cached tariff, it rebuilds
the complete schedule, as the app does. Without one, it tests the readable 28:75
word with a separate original-value backup and restore. No automatic address
fallback is used. Readback does not establish heating effects. See RESEARCH.md
and README.md for the app trace, owner-capture evidence and test workflow.
