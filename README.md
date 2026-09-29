# AO Smith Local BLE — development 0.3.2.dev0

Local Bluetooth integration for Home Assistant. No AO Smith account, password,
or Internet is needed for heater control. Optional tariff lookup contacts AO Smith’s
service only when requested in Configure; the selected plan is cached locally.

**Development preview.** Install through HACS as a custom repository or copy
its custom component manually. This repository is not in HACS's default catalog.

Repository: https://github.com/spikked27/AOSmith-BLE


## Supported hardware and validation

The wire protocol was extracted from iCOMM 14.1.0 and tested manually on an
AO Smith **HPS10-80H45DV**, reported firmware **6.4**, on September 28, 2026.
The owner confirmed authentication, setpoint/mode reads, water availability,
fault reads, and a Hybrid → Heat Pump → Hybrid change using nRF Connect.

The owner has now run this integration in Home Assistant for 30 minutes with
working controls and temperature status. The owner also verified a 125→124→125°F
setpoint change on the physical display, the Reconnect button, and reconnection
after restarting Home Assistant, both without touching the heater. It is
designed for other heaters using the same next-generation iCOMM register map.
An ICOMM advertisement alone does **not** establish compatibility. Older heat
pump models use different registers and are not supported by this release.

## Features

- Bluetooth discovery plus manual address entry.
- Guided, explicitly confirmed new local pairing or reuse of an existing pairing.
- Unique pairing identifier generated per setup; no shared or hardcoded credentials.
- Automatic challenge authentication on connection; renews expired sessions when
  a read returns the known session-expired response.
- 30-second polling (configurable 15–300 seconds).
- Water heater entity with Electric, Hybrid, Heat Pump, Vacation and Guest modes.
  Vacation selection means **on until changed**; Guest selection means **one day**.
- **Mode duration** on the device page, plus the **Set timed mode** action: Electric 1–99 days, Vacation 1–99 days or
  100 for continuously on, and Guest 1–7 days. These duration controls are
  APK-derived and awaiting hardware validation.
- Temperature controls default on for new setups, with register readback. The
  slider follows the heater-reported remote maximum, up to the HPS10 manual
  ceiling of 150°F. Missing/invalid maximum data retains the 140°F fallback.
  An existing explicit off preference is preserved.
- Cumulative **Energy usage** in kWh, suitable for HA energy statistics. The observed
  350.532 kWh agrees with the owner’s approximately 350 kWh app reading.
- Percentage availability with explicitly selected scale and fault-present status.
  Until calibrated the percentage is unknown; the raw byte remains in attributes.
  Duplicate setpoint/raw fault and
  extended register sensors are diagnostic and disabled by default for new entries.
  Existing entity IDs, history and user enable/disable choices are preserved.
- Optional remaining-days/setpoint diagnostics and model-specific Hot Water Plus.
- Anonymous ZIP → utility → tariff lookup, with a locally saved seasonal/holiday
  preview. It does **not** program a heater schedule or calculate tariff costs yet.
- Demand-response entities are retired; old ones are disabled without deleting history.
  Removing controls does not reset any previously changed heater flags.
- Refresh, Reconnect and **Inspect extended registers** diagnostic buttons.
- Redacted downloadable diagnostics, a timestamped extended-register capture,
  the last 60 protocol events, and 20 command outcomes kept separately from polls.
- Existing device pairings are never deleted. Routine reconnects never enroll keys.

Actual tank temperature, compressor state, fault descriptions, clock synchronization,
and utility-rate programming are not yet implemented. The setpoint is not presented
as measured tank temperature. Availability value 5 was observed. A five-level percentage estimate is now an
explicit option; it is not assumed for every heater. See calibration below. See
[FEATURES.md](FEATURES.md) for the full app-feature inventory and evidence gaps.

## Development status

This branch contains unreleased duration controls. It is not a completed feature
release and does not add clock synchronization or heater-owned tariff scheduling.
The published main branch remains 0.3.1. Keep your existing pairing and configuration.
See [VALIDATION.md](VALIDATION.md) for software tests versus physical acceptance.

## Configuration

**Settings → Devices & services → AO Smith Local BLE → Configure** now offers:

- **Controls and readings**: availability scale, polling interval, temperature writes, energy reads,
  extended diagnostic reads and model-specific Hot Water Plus.
- **Look up or replace a utility tariff**: enter a US ZIP, choose a utility and
  complete tariff, then confirm the local preview. ZIP is sent to the lookup
  service but not saved. For PSEG Long Island, choose **195 — Residential**
  (tariff ID 3439409), not the separate Power Supply Charge tariff.
- **Remove saved tariff**: removes only the local preview, with no heater writes.

The **Selected tariff** diagnostic entity shows the cached events, holidays and
retrieval timestamp even without Internet/Bluetooth. Failed or cancelled lookups
preserve the previous plan. There is no automatic online refresh, login or account
configuration. Use the lookup flow again to explicitly replace an outdated plan.

Read [RESEARCH.md](RESEARCH.md) for the temperature-limit, clock and official-integration
comparison, and [TARIFF.md](TARIFF.md) for schedule validation.
This version cannot yet make the heater follow the selected plan. Current mode
and temperature controls continue to work locally.

Energy and extended reads are optional: rejected registers do not invalidate
core readings, and transport errors back off for ten minutes. **Inspect extended
registers** retries known registers. Enable Hot Water Plus only on models that
actually offer it in iCOMM; the live mode is checked before each boost write.

### Setting Vacation, Guest or Electric duration

On this development branch, open the heater's device page:

1. Select **Vacation**, **Guest**, or **Electric** on the water-heater entity.
2. Use **Mode duration** in Controls to choose the number of days.
3. Read back the displayed countdown. Selecting another duration starts it from now.

Vacation offers 1–99 days or **Until changed**. Guest offers 1–7 days. Electric
offers 1–99 days or **Until changed**. The duration control is unavailable in
Hybrid/Heat pump. A live mode check prevents a stale UI from re-entering a mode
that somebody has since changed at the heater. Countdown polling remains enabled
for the active mode even with extended diagnostic reads switched off. An absent
or invalid countdown is unknown, not a remembered successful command.

In the currently published 0.3.1, use **Developer tools → Actions → AO Smith Local
BLE: Set timed mode**, select your integration entry, mode and days. This action
also remains available in automations. Vacation 100 means **Until changed**, not
100 days. For ordinary seven-day Vacation, enter 7.

The device owns its countdown; HA does not emulate it. The HPS10 manual specifies
that Vacation returns to the previous mode with nine hours remaining for recovery,
so its end should not be treated as exactly days × 24 hours. Changing back to Hybrid
or Heat pump exits a timed mode. Native Electric selection retains the previously
verified zero-duration encoding. Finite countdowns and their expiry behavior
still need physical confirmation; passing software tests alone is insufficient.

```yaml
action: aosmith_ble.set_timed_mode
data:
  config_entry_id: YOUR_LOCAL_INTEGRATION_ENTRY_ID
  mode: Vacation
  days: 7
```

The duration sensors retain the raw low-byte value: 100 may be the app's **On**
sentinel, so they are not advertised as elapsed-time measurements. Utility and
remaining-days controls/readings still need confirmation on real devices.

## Installation

### HACS custom repository

1. Open HACS → menu → Custom repositories.
2. Enter `https://github.com/spikked27/AOSmith-BLE`, category **Integration**.
3. Download **AO Smith Local BLE**, then restart Home Assistant.
4. Continue with the Bluetooth/setup steps below (starting at step 3).

### Manual install and setup

1. Put `custom_components/aosmith_ble` from this ZIP into
   `/config/custom_components/aosmith_ble` on Home Assistant. Avoid an extra nested
   `aosmith-ble` directory under `custom_components`.
2. Restart Home Assistant.
3. Provide Bluetooth coverage at the heater: a Home Assistant Bluetooth adapter
   or an ESPHome Bluetooth proxy with active connections. Proxy support follows
   HA's standard transport APIs but has not yet been tested with this heater.
4. Disconnect nRF Connect and close iCOMM so they release the heater connection.
5. Enable Bluetooth on the heater using its normal controls. Do not reset it.
6. Open **Settings → Devices & services → Add integration → AO Smith Local BLE**,
   or use the discovered entry.
7. Select the heater. Confirm the proposed six-digit PIN (derived from its
   advertised name); manual entry is available.
8. For a new installation choose **Create a new local pairing**. Leave the
   identifier blank to generate one. The next page displays it before enrollment;
   save it in case setup is interrupted. Existing testers choose **Reuse an
   existing local pairing** and enter their enrolled identifier exactly.
9. Confirm setup. The integration authenticates and reads the supported registers
   before creating the device. This does not change mode or temperature.

The enrolled identifier and PIN live in HA config-entry storage. Normal Home
Assistant backups preserve them. If a pairing request times out, Retry authenticates
with the same identifier instead of repeatedly enrolling it. If you abandon that
flow, preserve the displayed identifier and try the Existing pairing option.
If pair storage is full, this integration stops; it does not delete someone else's key.

## Hot-water availability calibration

The normal entity is **Hot water availability** in percent. The raw Bluetooth
value is retained in its `raw_value` attribute and diagnostics. Its unique ID
is unchanged; pre-upgrade raw history is not rewritten into percentages.

Use **Configure → Controls and readings → Hot-water availability scale**:

| Selection | Mapping | Raw 5 displays |
|---|---|---|
| Not calibrated (default) | No assumed conversion | Unknown; raw_value remains 5 |
| 0–5 levels | Estimated 20% per level | 100% |
| 0–100 percent remaining | Direct percentage | 5% |
| 0–100 percent used | Invert the percentage | 95% |

Choose a scale only after comparing with iCOMM, preferably both before and after
normal hot-water use. The APK exposes the BLE low byte without a percentage
conversion. The cloud client instead inverts its numeric API field, so a cloud
mapping cannot be blindly applied to BLE. Five-level conversion is provisional,
not a measurement of gallons or tank temperature. Values outside the selected
scale become unknown rather than being clamped to a misleading 0% or 100%.
No cross-calibration long-term statistics are generated for this sensor.

## Temperature panel

The water-heater temperature editor is enabled by default. If it was previously
disabled, enable **Configure → Enable temperature controls**. This is the native water-heater UI; a separate
climate/thermostat entity is not required. The **Temperature setpoint** sensor
shows the setting even while writes are disabled. It is not tank temperature.
The app and official HA integration both use the heater's reported remote maximum.
If HA shows a 125°F maximum, that is distinct from the product's 150°F capability.
The app's help directs users to increase the temperature using the physical
heater controls to raise the permitted remote maximum, then refresh. This changes
the actual setpoint; it is not merely a slider preference. No maximum-register
write or automatic temperature increase is performed by this integration.
The maximum is polled even with extended diagnostics disabled.

Vacation mode hides the temperature editor; both UI and transport require leaving
Vacation before changing setpoint. Mode selection remains available.

Recovery buttons remain available after failed polls so you can retry a disconnected
heater. Late notifications from closed sessions are discarded.

## Fast development/debug loop

1. On the integration entry, select **Enable debug logging**.
2. Reproduce one problem: refresh, a mode change, or the Reconnect button.
3. Select **Disable debug logging** to download the log, and **Download diagnostics**.
4. Report the approximate time, heater model/firmware, adapter/proxy type, what
   the physical display showed, and the expected result. Share both downloaded
   files. Integration diagnostics omit address, device name, PIN, pairing identifier,
   challenge bytes and authentication digest; full HA logs may contain other
   integrations' details, so review them before sharing publicly.

No proprietary phone APK is required for users to install this integration.
Debug frames are limited to ordinary register traffic, and sensitive handshake
events are represented only by opcode/status. The bounded event and command histories are
in memory and clear on reload/restart. Command outcomes distinguish not sent,
unconfirmed and confirmed by readback. A confirmed setting followed by a failed
refresh retains its confirmation in diagnostics; do not repeat the write blindly. There is no telemetry upload.

When replacing Python files during development, restart HA to guarantee new code
is imported. A configuration-entry Reload can reconnect an existing loaded
version but is not a reliable code hot-reload. Later HACS releases will make
updates simpler. Do not reinstall or recreate pairing for each update.

## Extended-register capture for energy research

1. Press **Inspect extended registers** on the integration's device page.
2. Wait for the action to finish, then **Download diagnostics**.
3. Note the time, active mode, whether the heater was heating, and any available
   app energy reading with its timestamp. If practical, repeat after a heating cycle.

The capture includes raw 16-bit words for the APK's `OADR_ELECTRIC_POWER_USAGE`,
`OADR_GRID_PRESENT_ENERGY_LEVEL` and `OADR_GRID_TOTAL_ENERGY_LEVEL` groups. The electrical-use group is now read together as a 48-bit Wh counter and exposed
as kWh. The two grid-energy groups still have unknown units and remain raw. The capture also includes candidate clock words (unverified for this profile). It
is read-only, contains a timestamp and per-register results, and clears on reload.
Capture/normal polling share one request queue. Pairing material is omitted.

## Hardware acceptance checklist

- Match target and mode to the physical display; compare availability.
- Change Hybrid ↔ Heat Pump and verify both physical display and subsequent read.
- Enable setpoint writes, test a small temporary change, and restore the original.
- Run for at least 15 minutes and inspect authentication/connection counters.
- Use Reconnect without pressing the heater button; repeat after a HA restart.
- Confirm whether Bluetooth needs a physical activation after long idle or a
  heater power interruption. Software cannot promise around a firmware radio timeout.
- Once stable, test with the heater's internet access blocked.

Read transport failures retry once with reconnect. Writes are never automatically
resent; success requires register readback. A lost write response may mean the
setting changed even if HA reports failure: refresh before trying again.

## Development

Use Python 3.13 and Home Assistant 2025.12.5 or later for the test environment.
Install HA's Bluetooth component dependencies as well as pytest, pytest-asyncio,
ruff, and the manifest requirements. Run `pytest` and `ruff check .`.
Tests use captured read-response fixtures and a simulated BLE peripheral; they
do not contact a heater. See `PROTOCOL.md` for the implementation assumptions.

## Roadmap

1. Validate new timed modes/optional features and proxy transport on real hardware.
2. Publish tagged releases after hardware testing; accept model/firmware
   reports without collecting credentials.
3. Add explicit protocol profiles for additional models, backed by captures/tests.
4. Check the energy counter over a heating cycle and through a heater restart.
5. Investigate local utility-rate/TOU scheduling (APK contains season/holiday
   block writers). Validate formats and readback before exposing any schedule write.
   This is distinct from tariff-based cost calculations in Home Assistant.

This is an independent integration, not affiliated with AO Smith.
