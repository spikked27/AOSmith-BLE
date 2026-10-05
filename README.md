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

Hot Water Plus can be enabled for models that support it. Version 1.3.0 adds an
experimental clock-set button, tariff lookup/upload, original-schedule restore,
and an opt-in energy-preference control. Diagnostic read status and integration
version sensors are enabled by default; four debug buttons are disabled by default.

## Requirements

- Home Assistant 2025.12 or newer.
- A supported local Bluetooth adapter, or an ESPHome Bluetooth proxy with active
  connections enabled, within range of the heater. Proxy support uses HA's
  Bluetooth infrastructure but has not been tested with this heater yet.
- Bluetooth enabled on the water heater and its six-digit pairing PIN.

No proprietary APK is needed. Normal heater control and polling are local.
Updates and optional tariff lookup require Internet access from Home Assistant;
tariff lookup uses AO Smith's anonymous service and requires no AO Smith account.

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

### Errors and clock setting

**Error status** reports the heater's current fault, including unknown codes.
Fault **42: Clock not set** means the heater reports an unset clock; an absent
fault does not verify its time or timezone.

**Set heater clock (experimental)** sends the current time in Home Assistant's
configured timezone, using the app's known two-word clock format at 26:3–4. It
records the initial read, write acknowledgement and readback in diagnostics.
An unsupported initial clock read does not prevent this explicitly requested
write trial. The next-generation clock mapping, continued ticking and DST
handling remain hardware-unverified. No clock write occurs on startup or polling.

### Utility tariffs and energy preferences (experimental)

1. Open **Settings → Devices & services → AO Smith Local BLE → Configure →
   Find and apply a tariff**. Enter your ZIP, utility and rate plan.
2. Choose **More Hot Water**, **More Savings**, or **Most Savings**. The clock
   option synchronizes local time before uploading; it can be unchecked when
   testing a schedule independently of the clock command.
3. Apply and leave the progress screen open until it finishes. The integration
   reads and saves all five season blocks plus holiday/preference data before
   sending any clock or schedule write, then verifies each written chunk.
4. **Restore original tariff schedule** restores that first saved schedule,
   including after HA restarts. A partial/ambiguous upload stops immediately;
   diagnostics identify the last chunk. No write is automatically repeated.

The lookup restores AO Smith's anonymous tariff API. The integration generates
the seasonal events from its returned prices using the recovered iCOMM algorithm.
The API supplies tariff data, not a universal fixed schedule for each preference.
Changing the preference changes event modes; time boundaries and load-up
placement follow tariff prices. The five stored season blocks include
all twenty event slots per block. Unsupported holiday IDs or malformed tariff
data stop generation before writing.

After a tariff has been applied, the **Energy preference (experimental)**
dropdown regenerates and uploads the complete cached tariff with the new
preference. This can take several minutes. It does not repeat the clock write.
Without a cached tariff, enabling the dropdown in **Controls and readings**
provides a single-word experiment at **28:75**. The owner's latest capture reads
that address successfully and rejects the former 28:113 candidate with status
0x40. There is no automatic alternate-address fallback.

The word-only experiment saves its original value separately before writing.
**Restore original preference word** restores only that word; use **Restore
original tariff schedule** to restore the complete schedule. Both backups
survive restarts. The preference control is opt-in; enabling it alone sends no writes.

Readback verifies stored bytes, not actual heating behavior or schedule activation.
Clock accuracy, DST and offline execution still need physical testing. There is
no periodic tariff refresh: repeat the lookup when you want updated service data.
Forgetting the cached tariff removes its HA configuration without changing the
heater's stored schedule or deleting its original backup.

## Configuration

**Settings → Devices & services → AO Smith Local BLE → Configure** offers:

- **Controls and readings:** polling interval (30 seconds by default, 15–300
  seconds), Hot Water Plus, and experimental energy preference.
- **Find and apply a tariff:** ZIP, utility, plan, preference and clock option.
- **Forget cached tariff:** removes the cached plan without writing to the heater.

Temperature controls, energy readings and active countdown polling are automatic.
No separate keepalive option is needed. The integration keeps its BLE connection
and reconnects/authenticates when necessary. Behavior after a heater power loss
or long radio idle period can depend on firmware.

## Updates and cleanup

Update through HACS, then **restart Home Assistant**. Keep the existing integration
and pairing; do not remove and re-add it for an update. A host/Unraid reboot is
not needed. Integration Reload reuses imported Python modules and cannot reliably
load an update. Once the release is running, settings changes reload the entry
automatically and tariff actions do not need an HA restart.

The **Integration version** sensor shows the running version. Its attributes
include the downloaded version and `restart_required`, so a downloaded update
that has not been loaded is visible after the next poll.

Version 1.1.0 fixes the shrinking temperature ceiling, defaults availability to
HPS10, and changes the Vacation control to Vacation/Guest mode. The update
**automatically removes obsolete entity-registry entries** left by earlier
versions: duplicate temperature/countdown sensors and old tariff, raw-fault and
demand-response entities. No manual purge is needed. Recorder history is not
purged. Remove any dashboard cards or automations you created for retired entities.

Four current debug buttons remain disabled by default: Refresh readings,
Reconnect Bluetooth, Inspect extended registers, and Read stored tariff schedule. These are optional tools,
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
**Inspect extended registers** and **Read stored tariff schedule** are read-only.
Watch **Diagnostic read status**: it changes to Reading, then Complete, Complete
with errors, Incomplete, or Failed. A persistent notification says when the read
has stopped and diagnostics can be downloaded. Rejected optional registers no
longer abort the remaining extended reads. The notification includes counts;
Complete with errors means the scan finished but some registers were rejected.

Diagnostic traffic histories and manual captures are bounded and cleared on
reload. Original preference/schedule backups and the last tariff operation are
stored persistently. Nothing is uploaded automatically.

## Development and support

Report issues at [GitHub Issues](https://github.com/spikked27/AOSmith-BLE/issues).
See [VALIDATION.md](VALIDATION.md) for hardware coverage and limitations,
[FEATURES.md](FEATURES.md) for scope, and [PROTOCOL.md](PROTOCOL.md) /
[RESEARCH.md](RESEARCH.md) for technical findings.

Tests use Python 3.13, HA 2025.12.5 and a simulated BLE device. The GitHub workflow
installs the required dependencies and runs Ruff, pytest and archive validation.
After editing Python code locally, restart HA; an integration Reload is not a
reliable code hot-reload.
