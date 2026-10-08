# AO Smith Local BLE

<img src="https://raw.githubusercontent.com/spikked27/AOSmith-BLE/main/custom_components/aosmith_ble/brand/logo.png" alt="A. O. Smith" width="240">

[![Release](https://img.shields.io/github/v/release/spikked27/AOSmith-BLE)](https://github.com/spikked27/AOSmith-BLE/releases)
[![Tests](https://github.com/spikked27/AOSmith-BLE/actions/workflows/tests.yml/badge.svg)](https://github.com/spikked27/AOSmith-BLE/actions/workflows/tests.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5?logo=homeassistant&logoColor=white)](https://hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home_Assistant-2025.12%2B-18BCF2?logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)

Control your A. O. Smith iCOMM heat-pump water heater locally from Home Assistant.
Set temperature and operating mode, manage electricity tariffs and savings
preferences, and track hot-water availability, energy use and heater errors.
No AO Smith account is required.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=spikked27&repository=AOSmith-BLE&category=integration)

**Tested:** HPS10-80H45DV, firmware 6.4. Other next-generation iCOMM heat pumps
may work but have not been verified. Older iCOMM families use different protocols.
This is an independent community integration, not an official A. O. Smith product.

## Features

| Feature | Description |
|---|---|
| Water heater | Temperature, Hybrid, Heat pump, Electric, Vacation and Guest modes |
| Mode duration | Electric and Guest: 1–7 days; Vacation: 1–99 days or Until changed |
| Savings preference | More Hot Water, More Savings or Most Savings; applies the complete tariff schedule |
| Electricity tariff | Current configured utility and rate, such as **PSEG 194** |
| Hot Water Plus | Off and levels 1–3, shown automatically when supported |
| Hot water level | Heater-reported Low, Medium or High; no claim of measured tank volume |
| Energy usage | Cumulative kWh, compatible with the Energy dashboard |
| Error status | Current fault description and code |
| Clock synchronization | Verifies tariff transitions, reports desync and permits one bounded correction |
| Active demand response | Current Baseline, DR1, DR2, DR3 or Load up status |
| Troubleshooting | Download diagnostics and read-only diagnostic actions; no diagnostic entities |

Version 3 keeps everyday controls on the device page and removes development
diagnostic buttons and status entities. Existing pairing credentials, entity identities and saved tariff data
carry forward when upgrading.

## Installation

### HACS

You need [HACS](https://hacs.xyz/) installed first. Use the blue button above to
open this repository in HACS, then download **AO Smith Local BLE**.

To add it manually:

1. Open **HACS → ⋮ → Custom repositories**.
2. Enter `https://github.com/spikked27/AOSmith-BLE` and select **Integration**.
3. Download **AO Smith Local BLE**.
4. Restart **Home Assistant Core**.
5. Open **Settings → Devices & services → Add integration → AO Smith Local BLE**.

### Manual

Download `aosmith_ble.zip` from [Releases](https://github.com/spikked27/AOSmith-BLE/releases).
Copy its `custom_components/aosmith_ble` folder into `/config/custom_components/`,
restart Home Assistant Core, then add the integration.

### Requirements

- Home Assistant **2025.12 or newer**.
- A supported Bluetooth adapter or ESPHome proxy with active connections enabled,
  within range of the water heater. Proxy support uses HA's shared Bluetooth
  infrastructure; this heater has not yet been tested through a proxy.
- Bluetooth enabled on the heater and its six-digit pairing PIN.

Normal control, polling and changes to an already configured savings preference
work locally. Downloading updates and looking up a new tariff require Internet.

## Connect your heater

1. Enable Bluetooth on the heater. Close iCOMM or other connected Bluetooth apps.
2. Choose the discovered heater, or enter its Bluetooth address manually.
3. Confirm its six-digit PIN.
4. Choose **Create a new local pairing** and leave the identifier blank. Save the
   generated identifier shown on the confirmation page.
5. Confirm setup. Home Assistant reads the heater and creates its device page.

For an existing pairing, choose **Reuse an existing local pairing** and enter its
exact identifier. Retry the same setup flow after a timeout. Existing pairings
are never deleted. Home Assistant backups preserve the credentials.

## Tariffs and savings

1. Open the integration's **Configure** gear.
2. Enter your ZIP code, choose your utility and rate plan, then select a savings
   preference. Lookup uses AO Smith's anonymous tariff service.
3. Submit and wait for completion. Home Assistant
   reads the complete stored schedule first. If all 678 bytes already match, it
   confirms the tariff without writing it again. Otherwise it uploads the generated
   schedule and checks each written portion. This can take several minutes.
4. **Electricity tariff** displays the configured plan, for example **PSEG 194**.
   Its attributes include the full utility and rate name, savings preference,
   update status and the last successful update time.

To change your savings preference later, use the **Savings preference** dropdown
on the device page. It rebuilds the entire cached schedule and shows a completion
notification. It does not require another tariff lookup or repeat clock setting.
The dropdown becomes available after a tariff has been configured.

The tariff sensor shows **Updating** during an upload and **Update incomplete**
if a write was interrupted or could not be confirmed. Check the connection and
apply the desired tariff again. The error detail identifies the failed stage and
whether any writes were sent. Slow write acknowledgements get the full eight-second
response window. A lost schedule/readback response gets one reconnect and read retry;
writes are never automatically replayed. The integration retains the original schedule
internally and does not automatically repeat writes or restore an old tariff.
A successfully applied tariff and preference survive Home Assistant restarts.

The heater stores the schedule. Home Assistant does not periodically download
rate updates; repeat the configuration flow when your utility changes its plan.
Tariff names reflect the plan applied through this integration. Changes made
later in iCOMM cannot be identified from the heater's stored schedule alone.

## Everyday controls

**Temperature:** use the standard water-heater control for **95–150°F**. This is
the target temperature; measured tank temperature is not available. Vacation
uses its own low temperature and hides temperature adjustment.

**Timed modes:** selecting Electric or Guest starts one day; Vacation starts
seven days. Adjust **Mode duration** after selecting the mode. Vacation also
supports **Until changed**. Choosing Off in Mode duration returns to Hybrid.
The heater owns the countdown, and changing the duration restarts it.

For automations, set mode and duration together:

```yaml
action: aosmith_ble.set_timed_mode
data:
  config_entry_id: YOUR_LOCAL_INTEGRATION_ENTRY_ID
  mode: Vacation
  days: 7
```

Electric and Guest accept 1–7 days. Vacation accepts 1–99, or 100 for Until changed.

**Hot water level:** Low, Medium and High are categories reported by the heater.
Low does not mean the tank contains no usable hot water. Other codes display
Unknown. If Low persists after heating, compare with iCOMM's indicator and actual
hot-water delivery; the integration cannot distinguish a stale heater estimate
from a genuine low level or measure the tank temperature.

The older percentage entity retains its identity and 0/50/100 values for existing
automations, and is renamed **Hot water availability index**. It is disabled by
default for new installations. Existing enabled entities are left enabled; you can
disable the index after updating your dashboard to Hot water level.

**Energy:** the cumulative kWh sensor can be added to the Energy dashboard.
Instantaneous power and historical cloud data are not provided.

**Clock:** **Automatic clock correction** is enabled by default. The integration
compares the selected tariff's value-changing boundaries with the heater's live
DR status. The **Clock synchronization** sensor shows progress and any detected
desync. Its attributes retain the last desync time, event count, correction outcome
and last verified transition, even after timing is verified again.

A check requires a fully confirmed tariff, Hybrid mode, clear utility/override
status, and fresh observations before and after the boundary. It allows three
minutes for the transition, then requires three mismatched readings spanning at
least one minute. It pauses for gaps, changed mode/setpoint, holidays and the
following day, season-change dates, and DST-change dates. Boundaries that keep
the same DR value cannot verify timing. Keep the default 30-second poll interval;
read gaps over 90 seconds invalidate a check.

A missed transition raises **Clock desync detected** and a persistent notification.
This is an inference from missed tariff execution, not a direct measurement of
clock drift. Before correction, the integration reads the complete device schedule
and checks that it still matches the saved tariff, then rereads live status. A
mismatch or changed conditions stops correction. An accepted clock write remains
**Clock set; awaiting verification** until a later on-time transition is observed.
There is at most one automatic write per unresolved desync episode and at most
one per 24 hours; the limit survives restarts and failed writes. A further missed
transition after a correction requires manual attention.

Turn Automatic clock correction off to keep detection without clock writes.
**Synchronize clock** remains available for an explicit manual setting using HA's
configured local timezone. Startup, reconnects and tariff uploads do not themselves
set the clock. Register 26:3–4 can retain the last written hour with zero minutes;
that readback is never used to infer drift.

**Active demand response** decodes the upper byte of register 27:0. An owner capture
observed DR1 → Baseline at the selected 22:00 tariff boundary. DR2, DR3 and Load up
labels follow the app's schedule encoding and still need equivalent live captures.
This sensor does not report which heating element or compressor is running.
Electric mode is not yet validated for tariff timing, so clock verification pauses
there; the integration does not promise that Electric heating stops at peak rates.

### Troubleshooting actions

Use **Settings → Devices & services → AO Smith Local BLE → Download diagnostics**
for current readings, clock verification/history, versions and saved evidence.
There are no diagnostic-only buttons or sensors on the public device page.

For additional evidence, open **Developer tools → Actions** and select the heater:

- **Capture DR status** reads one timestamped status snapshot.
- **Start DR monitoring** captures about once per minute for 1–360 minutes (default
  180); **Stop DR monitoring** ends the session early.
- **Inspect extended registers** reads the known diagnostic registers.
- **Read stored tariff schedule** reads all stored tariff bytes.

Wait for the completion notification before downloading diagnostics. Captures
include raw values, read errors, per-register timestamps, mode, setpoint and fault
context. A capture took about 30 seconds on the tested connection; it is not atomic.
The latest 400 DR captures survive restart. Monitoring stops on unload/restart and
does not resume itself. The actions only read registers; automatic clock correction
is a separate policy controlled by its switch. Unmapped values remain unmapped.

For an automation, the DR actions are `aosmith_ble.capture_dr_status`,
`aosmith_ble.start_dr_monitor` and `aosmith_ble.stop_dr_monitor`, targeted with
`config_entry_id`. The extended actions are `aosmith_ble.inspect_registers` and
`aosmith_ble.inspect_schedule`.

### Branding

AO Smith's existing Home Assistant brand assets are bundled for light/dark themes
and normal/high-density displays. Home Assistant 2026.3+ serves these locally.
The logo is also shown in the README/HACS detail page. The current HACS downloads
list still uses the old brands CDN and can show a placeholder for bundled custom
icons ([upstream issue](https://github.com/hacs/integration/issues/5223)); this
integration does not patch HACS. Older HA versions retain their previous icon.

## Updates and troubleshooting

Update through HACS and restart **Home Assistant Core** to load new Python code.
There is no need to reboot the host or remove and pair the integration again.
Tariff changes and everyday settings take effect without restarting Home Assistant.
Use **⋮ → Reload** for an integration reconnect; reload does not load newly
downloaded Python modules.

If the heater is unavailable, enable its Bluetooth, check adapter/proxy range
and close any other app using the connection. Keep the existing pairing identifier.

Upgrading to 3.0 removes retired development diagnostic entities, including any
that were previously enabled. Automations using those buttons must switch to the
actions listed above. Pairing, tariff backups, diagnostic history and normal
control identities are preserved. Running/downloaded versions are available in
Download diagnostics.

Report issues with your heater model, firmware, HA/integration version and
relevant logs at [GitHub Issues](https://github.com/spikked27/AOSmith-BLE/issues).
Review diagnostics before posting publicly; downloaded diagnostics redact pairing
credentials and the Bluetooth address but contain tariff and timing information.

## Project documentation

- [Feature coverage](FEATURES.md) and [validation](VALIDATION.md)
- [Changelog](CHANGELOG.md) and [latest release notes](RELEASE_NOTES.md)
- [Protocol reference](PROTOCOL.md)
- [Onboarding, tariff and clock research](research/ONBOARDING_AND_TOU.md)
- [Contributing](CONTRIBUTING.md)
