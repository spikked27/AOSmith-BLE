## AO Smith Local BLE 1.0.0

Local Home Assistant control for compatible next-generation iCOMM heat pumps,
with HPS10-80H45DV firmware 6.4 as the hardware-tested model.

- **One-step Vacation:** choose days to enter Vacation and set its timer together.
  Until changed stays in Vacation; Off returns to Hybrid.
- Native mode and temperature controls follow the live heater maximum, up to
  150°F. Active countdown and energy reads are automatic.
- Five everyday entities: water heater, Vacation, hot-water availability, energy
  usage and Error status. Hot Water Plus remains opt-in for supported models.
- One Error status indicator includes clock-not-set code 42. No speculative clock,
  tariff or demand-response writes.
- Refresh, reconnect and inspection buttons disabled by default; enable them when
  debugging. Redacted diagnostics preserve command outcomes and raw readings.
- Obsolete settings and duplicate entities retired; existing pairing is retained.

### Upgrade

Update in HACS and **restart Home Assistant**. Do not remove/re-pair the heater.
For HPS10, choose **Configure → Hot-water availability scale → HPS10 observed
categories**: High = 100%, Medium = 50%. Old speculative scales reset to Not
calibrated. The Low wire code is unknown; no evidence establishes -5 as Low or a
fault. Unknown availability values remain unknown.

The draft Mode duration entity is replaced by Vacation. Adjust any automations
using that draft entity; the Set timed mode action remains available. Debug buttons
are disabled once on upgrade, and later user enabling is preserved.

### Known limits

Finite Vacation/Guest/Electric countdowns and the new duration UI are software-tested,
not yet hardware-validated. Additional models and active proxy transport remain
unverified. Clock synchronization and heater-owned tariff scheduling are outside
this release; use iCOMM for utility setup. See VALIDATION.md for the evidence.

Install through the HACS custom repository, or extract the attached ZIP's
custom_components/aosmith_ble folder into /config/custom_components/aosmith_ble.
