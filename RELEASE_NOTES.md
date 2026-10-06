# AO Smith Local BLE 2.1.0

The integration now maintains the water heater's time automatically.

- Checks at startup, after connection recovery and every 15 minutes.
- Rechecks on the next normal poll after Home Assistant's timezone or DST offset changes.
- Synchronizes an unset/invalid clock or detectable drift; full minute readback
  allows a two-minute tolerance.
- Handles the HPS10 zero-minute response without a repeated-correction loop.
  Matching date/hour is partial readback, with a daily time refresh while connected.
- Persists correction history and retry limits across restart. Failed corrections
  wait at least an hour; normal controls remain usable when clock reads fail.
- Hides the manual clock button by default. Inspection controls stay available for
  the remaining physical test; extra diagnostic entities will be removed after testing.

Update through HACS and restart Home Assistant Core once. If you are collecting
an independent clock-ticking test, finish that capture on **2.0.0** before updating:
automatic correction can conceal whether the heater advances time by itself.

The software test suite covers clock drift, DST, partial readback, daily refresh,
failed reads, disk failure, cancellation, restart persistence and existing controls.
Physical RTC ticking and heating-event timing still require owner testing.
No extra options, entities or user automations are required for clock maintenance.
Standard Download diagnostics includes the maintenance record.
