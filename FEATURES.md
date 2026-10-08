# Feature coverage

Version 3.0.0 targets next-generation iCOMM heat pumps. The tested heater is an
HPS10-80H45DV with firmware 6.4.

| Feature | Status |
|---|---|
| Local pairing, authentication and reads | Hardware confirmed |
| Temperature and operating mode | Readback checked; basic mode changes hardware confirmed |
| Vacation, Guest and Electric duration | Implemented; finite expiry needs hardware validation |
| Hot Water Plus | Automatically exposed when its register supports it |
| Hot water level | Hardware-observed raw 0/5/10 shown as Low/Medium/High |
| Availability index | Legacy 0/50/100% entity retained for existing automations |
| Cumulative energy | kWh reading; Energy dashboard compatible |
| Faults | Known descriptions and explicit unknown codes |
| Tariff lookup | Anonymous AO Smith API; actual Rate 194/195 inputs captured |
| Tariff upload | Full 678-byte readback confirmed on hardware |
| Savings preference | Rebuilds all season, holiday and preference data |
| Active demand response | 27:0 upper byte; DR1 → Baseline observed live |
| Clock verification | Fresh tariff-boundary observation with persistent desync status/history |
| Clock correction | Bounded, schedule-checked automatic correction plus manual button |
| Troubleshooting | Download diagnostics and explicit read-only actions; no diagnostic entities |
| Branding | Bundled HA 2026.3+ assets and README/HACS detail-page logo |

Automatic correction is enabled by default and can be disabled without disabling
detection. It requires Hybrid mode and a confirmed matching tariff, tolerates
three minutes of delay, and makes at most one attempt per unresolved episode and
one per 24 hours. It does not use register 26:3–4 as a running clock. A later
on-time DR transition verifies timing within the configured tolerance.

DR2/DR3/Load up status labels follow app schedule encoding; live hardware evidence
currently covers DR1 and Baseline. Heating effects, Electric-mode tariff behavior,
clock-repair effectiveness and DST recovery still require physical validation.

Not implemented: measured tank temperature/volume, live compressor/element
activity, cloud history, Wi-Fi onboarding, utility enrollment or legacy protocols.
No public raw-write parameters or restore controls are provided.

The 3.0 upgrade removes development diagnostic entities, preserves normal controls
and saved evidence, and retains read-only troubleshooting through Actions.
