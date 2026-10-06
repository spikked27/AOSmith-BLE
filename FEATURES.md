# Feature coverage

Version 2.1.0 targets next-generation iCOMM heat pumps. The tested heater is an
HPS10-80H45DV with firmware 6.4.

| Feature | Status |
|---|---|
| Local pairing, authentication and reads | Hardware confirmed |
| Temperature and operating mode | Implemented with readback; basic mode changes hardware confirmed |
| Vacation, Guest and Electric duration | Implemented; finite expiry needs hardware validation |
| Hot Water Plus | Automatically exposed when its register reports a supported level |
| Availability | HPS10 0/5/10 categories hardware confirmed |
| Cumulative energy | kWh reading implemented |
| Faults | Known descriptions and explicit unknown codes |
| Tariff lookup | Anonymous AO Smith API; actual Rate 194/195 responses captured |
| Tariff schedule upload | Rate 194 / More Hot Water confirmed across all 678 stored bytes |
| Savings preference | Rebuilds all season, holiday and preference data; persists confirmed plan |
| Tariff display | Cached applied plan, compact label, preference and update status |
| Automatic clock maintenance | Startup/recovery/15-minute checks, local timezone/DST correction, and daily refresh for zero-minute readback |
| Diagnostic reads | Disabled by default, with completion notification and optional status sensor |
| Integration reload | Supported for settings/reconnection; new code requires Core restart |

Three savings choices use the app's recovered schedule generation, with boundaries
from the selected tariff. They do not share one fixed universal schedule.
Actual schedule activation, clock ticking/DST and heating effects remain physically
unverified. Readback confirms storage, not resulting heating behavior.

Not implemented: measured tank temperature, live compressor/element activity,
cloud history, Wi-Fi onboarding, demand-response enrollment or unsupported legacy
heater families. There are no public restore controls or raw-register parameters.

Manual clock synchronization is disabled by default. Extra diagnostic entities
remain only until the current hardware testing is complete.

Original backups and detailed command evidence remain available internally for
support. Existing opt-in diagnostic buttons are preserved on upgrade.
