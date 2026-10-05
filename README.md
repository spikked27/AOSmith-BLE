# AO Smith Local BLE

A custom Home Assistant integration for controlling compatible A. O. Smith iCOMM
heat-pump water heaters over Bluetooth. Change temperature and operating mode,
set Vacation/Guest duration, and monitor hot-water availability, energy use and
heater errors without an AO Smith account or cloud connection.

**Tested hardware:** HPS10-80H45DV, firmware 6.4. Other next-generation iCOMM
heaters may be compatible but have not been verified. Older iCOMM families use
different protocols. This project is independent of A. O. Smith.

## What you get

| Entity | What it does |
|---|---|
| Water heater | Sets temperature and selects Hybrid, Heat pump, Electric, Vacation or Guest |
| Vacation/Guest mode | Adjusts the active Vacation or Guest countdown; shows Off in other modes |
| Hot water availability | High = 100%, Medium = 50%, Low = 0%, using the HPS10 mapping |
| Energy usage | Cumulative electricity use in kWh; supports the HA Energy dashboard |
| Error status | Indicates a reported heater fault and provides its description and code |

Hot Water Plus can be enabled for models that support it. Diagnostic buttons are
available when needed and disabled by default. No tariff or demand-response
controls are included.

## Requirements

- Home Assistant 2025.12 or newer.
- A supported local Bluetooth adapter, or an ESPHome Bluetooth proxy with active
  connections enabled, within range of the heater. Proxy support uses HA's
  Bluetooth infrastructure but has not been tested with this heater yet.
- Bluetooth enabled on the water heater and its six-digit pairing PIN.

No proprietary APK is needed. Normal heater control and polling are local;
installing and downloading updates requires Internet access.

## Install with HACS

This integration is installed as a **custom repository**:

1. Open **HACS → ⋮ → Custom repositories**.
2. Add `https://github.com/spikked27/AOSmith-BLE` and choose **Integration**.
3. Find **AO Smith Local BLE** in HACS and download the latest release.
4. Restart Home Assistant.
5. Open **Settings → Devices & services → Add integration → AO Smith Local BLE**.

For manual installation, download `aosmith_ble.zip` from
[Releases](https://github.com/spikked27/AOSmith-BLE/releases), place its
`custom_components/aosmith_ble` folder in `/config/custom_components/`, and
restart Home Assistant.

## Connect your heater

1. Enable Bluetooth using the heater's controls. Close iCOMM and disconnect
   nRF Connect or other apps so they release the connection.
2. Select the discovered heater. If it does not appear, retry the scan or enter
   its Bluetooth address manually.
3. Check the suggested six-digit PIN against your heater's pairing information.
4. For a new installation, choose **Create a new local pairing** and leave the
   identifier blank. Save the identifier displayed on the confirmation page.
5. Confirm setup. The integration connects and reads the heater before creating
   the device. Setup does not change temperature or mode.

If you already enrolled an identifier, choose **Reuse an existing local pairing**
and enter it exactly. If enrollment times out, retry the same flow; do not keep
creating new identifiers. Existing heater pairings are never deleted. HA backups
preserve the credentials needed to reconnect.

## Everyday use

### Temperature and operating mode

Open the water-heater entity to select a mode or set the temperature. The
supported HPS10 range is **95–150°F**. The ceiling stays fixed when you lower the
setpoint; no temperature-enable or maximum-temperature setting is needed.
Commands are checked against the heater's readback before success is reported.
The temperature shown is the **setpoint**, not measured tank temperature.

Vacation maintains its own low temperature, so temperature adjustment is hidden
until you leave Vacation. Selecting a mode does not indicate whether the
compressor or heating elements are currently running; that status is not decoded.

### Vacation and Guest duration

1. Select **Vacation** or **Guest** on the water-heater entity.
2. The **Vacation/Guest mode** dropdown follows the selected mode and shows its
   reported duration. Selecting Vacation in HA starts **7 days**; Guest starts
   **1 day**.
3. Adjust the dropdown: Vacation supports **1–99 days** or **Until changed**;
   Guest supports **1–7 days**.
4. Select Hybrid, Heat pump or Electric on the water heater to leave the timed
   mode. The duration dropdown returns to **Off**. Choosing Off in the dropdown
   also exits the timed mode, selecting Hybrid.

Changing days restarts the active mode's countdown. The heater owns the timer;
HA does not emulate an expiry timestamp. Changes made at the heater or in iCOMM
appear after the next poll. Missing countdown data is unknown, not an invented
remaining duration. Finite countdown expiry remains hardware-unverified.

For automations, **AO Smith Local BLE: Set timed mode** sets mode and duration
in one action. It also supports timed Electric for 1–7 days:

```yaml
action: aosmith_ble.set_timed_mode
data:
  config_entry_id: YOUR_LOCAL_INTEGRATION_ENTRY_ID
  mode: Vacation
  days: 7
```

Vacation `days: 100` means Until changed. The HPS10 manual describes returning
from Vacation with nine hours left for recovery, so days are not an exact return
appointment.

### Availability and energy

Availability uses the HPS10 category mapping automatically:

| Raw Bluetooth value | Category | Display |
|---|---|---|
| 10 | High | 100% |
| 5 | Medium | 50% |
| 0 | Low | 0% |

There is no calibration setting. These percentages label categories, not measured
remaining gallons. Low is an availability reading, not a heater fault; 0% does
not mean the tank is empty. Other raw codes display Unknown. Raw values remain
in the entity attributes and diagnostics. Version 1.1.1 corrects the earlier
mapping; existing recorded history is not rewritten.


**Energy usage** reports cumulative kWh and can be added to the Energy dashboard.
It does not import cloud history or provide instantaneous power measurements.

### Errors, clock and utility tariffs

**Error status** reports the heater's current fault, including unknown codes.
Open the entity for the description and code. Fault **42: Clock not set** includes
instructions to connect the heater to the Internet through the official iCOMM
app, then reconnect BLE and check that the fault clears. A persistent clock fault
needs the manufacturer's setup/troubleshooting procedure. This integration does
not set the heater's clock, and an absent fault does not verify time or timezone.

Use iCOMM to configure utility plans and heater-owned schedules. **An offline
heater cannot receive updated tariff data from the service.** Its stored schedule
may continue, but this integration neither refreshes it nor verifies that its
rates, holidays or seasonal rules remain current. Local control does not
require cloud access; keeping a utility plan current may require reconnecting
through the official app. We have not verified whether iCOMM refreshes existing
plans automatically or requires reapplying them.

### Energy usage preferences

The iCOMM choices **More Hot Water**, **More Savings**, and **Most Savings**
control how the heater uses energy across an existing rate plan. They are
separate from Hybrid/Heat pump/Electric operating modes. The app warns that
Most Savings may leave insufficient hot water.

Preference control is **not yet available in this integration**: the APK uses
conflicting register addresses for newer heaters. Version 1.1.2 adds a targeted
read-only capture to the existing **Inspect extended registers** button to
resolve this. To contribute a comparison:

1. Update and restart Home Assistant. Enable **Inspect extended registers** on
   the device page if it is disabled.
2. Press it, wait for the action to finish, and download integration diagnostics.
   Note the preference currently shown in iCOMM.
3. Change the preference in iCOMM (for example, Most Savings to More Hot Water)
   and wait for the app to confirm it was applied. Inspect again and download
   a second diagnostics file, noting the new preference.

If iCOMM needs a Bluetooth connection, temporarily disable the HA integration
while using it, then re-enable HA before the second capture. Use the official
app's supported setup/connection flow if it requires Internet access. Inspection
makes no heater-setting changes, adds no entities, and is not part of regular
polling. A matching read alone does not prove a writable preference control;
we will verify a single-setting write separately before exposing it.

## Configuration

**Settings → Devices & services → AO Smith Local BLE → Configure** offers:

- **Polling interval:** 30 seconds by default; adjustable from 15 to 300 seconds.
- **Hot Water Plus:** enable only if your heater offers this feature in iCOMM.

Temperature controls, energy readings and active countdown polling are automatic.
No separate keepalive option is needed. The integration keeps its BLE connection
and reconnects/authenticates when necessary. Behavior after a heater power loss
or long radio idle period can depend on firmware.

## Updates and cleanup

Update through HACS, then **restart Home Assistant**. Keep the existing integration
and pairing; do not remove and re-add it for an update.

Version 1.1.0 fixes the shrinking temperature ceiling, defaults availability to
HPS10, and changes the Vacation control to Vacation/Guest mode. The update
**automatically removes obsolete entity-registry entries** left by earlier
versions: duplicate temperature/countdown sensors and old tariff, raw-fault and
demand-response entities. No manual purge is needed. Recorder history is not
purged. Remove any dashboard cards or automations you created for retired entities.

Three current debug buttons remain disabled by default: Refresh readings,
Reconnect Bluetooth, and Inspect extended registers. These are optional tools,
not abandoned entities. User-enabled debug buttons remain enabled on later updates.

## Troubleshooting

- **Heater not found:** enable its Bluetooth, disconnect phone apps, and check
  adapter/proxy range. A connected heater may stop advertising.
- **Pairing failed:** verify PIN and identifier. Retry uses the same identifier
  rather than repeatedly filling pairing slots.
- **Unavailable:** check Bluetooth coverage. Connection failures make readings
  unavailable; they do not report zero energy or a healthy heater.
- **Command failed:** refresh before repeating it. A lost response can mean the
  setting changed without confirmation. Writes are not automatically replayed.

For a report, enable **debug logging** on the integration entry, reproduce the
problem, then disable logging to download the log and select **Download
diagnostics**. Include model, firmware, adapter/proxy type, time and physical
heater reading. Diagnostics omit pairing secrets; review full HA logs before
sharing because other integrations may include private details.

To use a debug button, open **Settings → Devices & services → Entities**, show
disabled entities, filter by this integration, and enable the required button.
Inspect extended registers is read-only. Diagnostic histories are bounded, kept
in memory and cleared on reload. Nothing is uploaded automatically.

## Development and support

Report issues at [GitHub Issues](https://github.com/spikked27/AOSmith-BLE/issues).
See [VALIDATION.md](VALIDATION.md) for hardware coverage and limitations,
[FEATURES.md](FEATURES.md) for scope, and [PROTOCOL.md](PROTOCOL.md) /
[RESEARCH.md](RESEARCH.md) for technical findings.

Tests use Python 3.13, HA 2025.12.5 and a simulated BLE device. The GitHub workflow
installs the required dependencies and runs Ruff, pytest and archive validation.
After editing Python code locally, restart HA; an integration Reload is not a
reliable code hot-reload.
