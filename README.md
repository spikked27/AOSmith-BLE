# AO Smith Local BLE — experimental 0.1.0

Local Bluetooth integration for Home Assistant. No AO Smith account, password,
cloud API, or internet request is used by the integration at runtime.

**Development preview.** Install through HACS as a custom repository or copy
its custom component manually. This repository is not in HACS's default catalog.

Repository: https://github.com/spikked27/AOSmith-BLE


## Supported hardware and validation

The wire protocol was extracted from iCOMM 14.1.0 and tested manually on an
AO Smith **HPS10-80H45DV**, reported firmware **6.4**, on September 28, 2026.
The owner confirmed authentication, setpoint/mode reads, water availability,
fault reads, and a Hybrid → Heat Pump → Hybrid change using nRF Connect.

This Python integration still needs its first end-to-end hardware run. It is
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
- Water heater entity: target temperature and mode, with Electric, Hybrid and
  Heat Pump controls. Vacation/Guest are readable but their duration controls are
  deferred.
- Setpoint writing can be enabled in Options for hardware testing; it is disabled
  by default because the encoding is APK-derived but a temperature write has not
  yet been tested. Initial allowed range is 95–140°F; readback verifies the result.
- Raw hot-water availability level and fault-register sensors.
- Refresh and Reconnect diagnostic buttons.
- Redacted downloadable diagnostics with the last 60 protocol events.
- Existing device pairings are never deleted. Routine reconnects never enroll keys.

Actual tank temperature, compressor state, fault descriptions, energy kWh, and
utility-rate programming are not yet implemented. The setpoint is not presented
as measured tank temperature. Availability value 5 was observed; the proposed
0–5 → 0–100% conversion remains unverified and is not applied.

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
events are represented only by opcode/status. The bounded event history is
in memory and clears on reload/restart. There is no telemetry upload.

When replacing Python files during development, restart HA to guarantee new code
is imported. A configuration-entry Reload can reconnect an existing loaded
version but is not a reliable code hot-reload. Later HACS releases will make
updates simpler. Do not reinstall or recreate pairing for each update.

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

1. Hardware-test HA authentication, proxy transport, timeout recovery and setpoint writes.
2. Publish tagged releases after hardware testing; accept model/firmware
   reports without collecting credentials.
3. Add explicit protocol profiles for additional models, backed by captures/tests.
4. Decode local power/energy registers and compare against the cloud kWh baseline.
5. Investigate local utility-rate/TOU scheduling (APK contains season/holiday
   block writers). Validate formats and readback before exposing any schedule write.
   This is distinct from tariff-based cost calculations in Home Assistant.

This is an independent integration, not affiliated with AO Smith.
