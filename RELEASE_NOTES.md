## AO Smith Local BLE 1.1.0

### Fixes and changes

- Fix the temperature ceiling following the current setpoint downward. The HPS10
  temperature editor now uses a stable 95–150°F range. Every write still requires
  heater readback confirmation; Vacation's temperature guard remains.
- Change the duration control to **Vacation/Guest mode**. Select the mode on the
  water-heater entity first: Vacation starts at 7 days, Guest at 1 day. Adjust its
  duration in the dropdown. Other operating modes show Off; choosing Off exits
  to Hybrid.
- Use HPS10 hot-water availability categories automatically (High 100%, Medium
  50%). Remove the calibration option. Unknown codes remain unknown.
- Automatically remove obsolete diagnostic/duplicate entity-registry entries
  instead of leaving them disabled. Current debug buttons remain opt-in. Existing
  pairing and recorder history are not purged.
- Add recommended recovery steps to clock fault 42: connect through the official
  iCOMM app with Internet access, then verify the fault clears.
- Rewrite the README for installation, setup, everyday controls and troubleshooting.

Tariff lookup/programming remains excluded. Offline heaters cannot receive new
service tariff data; stored schedules are not verified or refreshed by this
integration. Whether iCOMM automatically updates an existing plan is unverified.

### Update

Download 1.1.0 in HACS and restart Home Assistant. Keep your current integration
and pairing. No availability configuration or manual entity purge is needed.
Remove any user-created dashboard cards/automations targeting retired entities.
The existing Vacation control keeps its unique ID and is renamed Vacation/Guest
mode unless you supplied a custom name.

### Validation

142 automated tests, Ruff checks and archive validation pass locally. Regression
coverage includes lowering from 125 to 124 then raising to 125/140/150, mode-aware
durations, clock guidance and removal of only owned retired entities. Temperature
writes above 125 and finite countdown expiry still need physical confirmation;
software tests are not hardware validation. HPS10-80H45DV firmware 6.4 remains
the tested model. Additional models/proxies and Hot Water Plus remain unverified.
