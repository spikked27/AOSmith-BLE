# AO Smith Local BLE

Control a compatible A. O. Smith water heater locally from Home Assistant over
Bluetooth. No AO Smith account or Internet connection is required for these
controls. Install **v1.0.0** through HACS as a custom repository.

Tested on **HPS10-80H45DV, firmware 6.4**. Other next-generation iCOMM heat pumps
may share this protocol but are not yet verified. Older iCOMM families use
different register maps and are not supported. This is an independent project,
not affiliated with A. O. Smith.

## Everyday controls

| Entity | Function |
|---|---|
| Water heater | Temperature and Electric, Hybrid, Heat pump, Vacation or Guest mode |
| Vacation | Choose days to enter Vacation in one step; shows the heater's remaining days |
| Hot water availability | Observed HPS10 High/100% and Medium/50% categories |
| Energy usage | Cumulative local kWh, usable in Home Assistant's Energy dashboard |
| Error status | Current heater fault, with a description; includes clock-not-set code 42 |

Hot Water Plus is an optional control for models that offer it. Debug buttons
are disabled by default. There are no duplicate temperature/countdown sensors,
tariff entities, or demand-response controls.

### Vacation in one step

On the device page, open **Vacation** and select **7 days**, for example.
That single selection enters Vacation and sets the timer together. You do not
need to change the water-heater mode first.

- **1–99 days:** start or restart the heater's countdown.
- **Until changed:** stay in Vacation indefinitely.
- **Off:** leave Vacation and select Hybrid. If already outside Vacation, do nothing.

The control displays the device's reported countdown, not an HA expiry timer.
The HPS10 manual describes returning to the previous mode with nine hours left
for recovery; do not interpret the timer as an exact return timestamp. Choosing
Vacation in the native water-heater mode menu still means **Until changed**.

For automations, or timed Guest/Electric operation, use **AO Smith Local BLE:
Set timed mode**. It accepts mode and days in one action: Guest/Electric 1–7,
Vacation 1–99, or Vacation 100 for indefinite operation.

```yaml
action: aosmith_ble.set_timed_mode
data:
  config_entry_id: YOUR_LOCAL_INTEGRATION_ENTRY_ID
  mode: Vacation
  days: 7
```

Finite countdown encoding and confirmation are software-tested and APK-derived;
physical countdown/expiry behavior remains unverified. Selecting Guest in the
native mode menu starts one day. Ordinary Electric selection is untimed.

### Temperature and availability

Temperature controls are always enabled outside Vacation. The slider honors the
heater's reported remote maximum, up to 150°F. If the heater reports 125°F as
its maximum, the integration will not bypass it. The app's instructions use the
physical controls to raise that allowance; doing so changes the actual setpoint.
No measured tank temperature is available, so the setpoint is not presented as one.

In **Configure → Hot-water availability scale**, select **HPS10 observed
categories** for the tested model. Raw 5 maps to High/100%; raw 0 maps to
Medium/50%, matching nearby app and official-HA observations. These percentages
are category labels, not measured remaining gallons. **Low's BLE code is still
unknown**, and other codes remain unknown rather than becoming a false 0% or fault.
Other models default to **Not calibrated**. The raw value remains in attributes.

## Install and connect

Requires Home Assistant **2025.12 or later**, plus a Bluetooth adapter or an
ESPHome Bluetooth proxy with active connections in range of the heater. Proxy
transport uses HA's standard APIs but has not been hardware-tested here.

1. In **HACS → Custom repositories**, add
   `https://github.com/spikked27/AOSmith-BLE` with category **Integration**.
2. Download **AO Smith Local BLE** and restart Home Assistant.
3. Enable Bluetooth on the heater. Close iCOMM and disconnect nRF Connect so they
   release their connection. Do not reset the heater.
4. Go to **Settings → Devices & services → Add integration → AO Smith Local BLE**.
   Choose the discovered heater, scan again, or enter its Bluetooth address.
5. Verify the suggested six-digit PIN. For a new installation, choose **Create a
   new local pairing** and leave the identifier blank. Save the generated
   identifier shown on the confirmation page before continuing.
6. Confirm. Setup authenticates and reads the heater without changing its mode
   or temperature. Open **Configure** and select the availability profile.

For manual installation, extract the release ZIP's `custom_components/aosmith_ble`
folder into `/config/custom_components/aosmith_ble`, then restart HA.

If enrollment times out, retry uses the same identifier instead of enrolling
repeatedly. If you abandon setup, use **Reuse an existing local pairing** with
that exact identifier. Existing pairings are never deleted. Normal HA backups
preserve the integration's PIN and identifier.

### Updating an existing installation

Download the update in HACS and **restart Home Assistant**. Keep your existing
integration and pairing; do not remove/re-add them.

Version 1.0.0 removes obsolete options and disables retired tariff, demand-response,
raw-fault, duplicate-temperature and countdown entities without deleting history.
Old debug buttons are disabled once during migration; you can enable them again.
The new Vacation control replaces the draft Mode duration entity. Update any
automations targeting that draft entity; the `set_timed_mode` action is unchanged.
Old speculative availability scales reset to Not calibrated: select **HPS10
observed categories** on the tested model. Core entity identities are retained.

## Settings and connection behavior

Only three options remain: availability profile, polling interval (default 30
seconds, range 15–300), and model-specific Hot Water Plus. Maximum temperature,
energy, and active countdown reads are automatic. Unsupported optional registers
do not make the core controls fail.

The integration keeps a connection and polls, reconnecting and authenticating
when necessary. No separate keepalive setting is needed. Read failures retry
once; writes are never automatically replayed and require readback confirmation.
After a lost write response, refresh before repeating a command: it may already
have reached the heater. Radio behavior after long idle or a power interruption
still depends on the heater's firmware.

## Errors, clock and utility plans

**Error status** reports the current fault, including unknown nonzero codes.
Attributes include the code, description and `clock_not_set`. Connection failure
makes readings unavailable; it does not report a false healthy state. This is
one current fault, not an alarm history.

Clock setting, heater-owned schedules and tariff programming are not implemented.
Use the official iCOMM app for utility setup. The integration does not clear or
rewrite existing heater schedules. Fault 42 can identify an unset clock, but a
clear fault cannot establish correct time or timezone. Offline TOU timing is not
guaranteed. HA-owned automations use Home Assistant's clock and require HA/BLE
availability when a command is due.

## Troubleshooting and development

1. On the integration entry, enable **debug logging** and reproduce the issue.
2. Disable debug logging to download the log, then **Download diagnostics**.
3. If needed, enable a debug button from **Settings → Devices & services →
   Entities**, filtering by this integration and disabled entities. Available
   buttons are **Refresh readings**, **Reconnect Bluetooth**, and read-only
   **Inspect extended registers**. Disabled entities can be hidden by default.
4. Include model/firmware, adapter/proxy type, approximate time, expected behavior
   and the physical display reading when reporting an issue.

Diagnostics omit addresses, device names, PINs, pairing identifiers and handshake
secrets. They retain the full availability word, optional-register results and
bounded in-memory protocol/command histories. Review full HA logs before sharing;
other components can include private data. Nothing is uploaded automatically.

Development uses Python 3.13 and HA 2025.12.5; see the test workflow for dependency
installation. Run `ruff check .`, `ruff format --check .` and `pytest -q`.
Restart HA after replacing Python files; entry Reload does not reliably reload code.

See [VALIDATION.md](VALIDATION.md) for tested behavior and remaining hardware
limits, [FEATURES.md](FEATURES.md) for scope, and [RESEARCH.md](RESEARCH.md) /
[PROTOCOL.md](PROTOCOL.md) for protocol evidence. Users do not need the APK.
