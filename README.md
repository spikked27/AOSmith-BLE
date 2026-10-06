# AO Smith Local BLE

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

| Control or reading | Description |
|---|---|
| Water heater | Temperature, Hybrid, Heat pump, Electric, Vacation and Guest modes |
| Mode duration | Electric and Guest: 1–7 days; Vacation: 1–99 days or Until changed |
| Savings preference | More Hot Water, More Savings or Most Savings; applies the complete tariff schedule |
| Electricity tariff | Current configured utility and rate, such as **PSEG 194** |
| Hot Water Plus | Off and levels 1–3, shown automatically when supported |
| Hot water availability | Low, Medium and High displayed as 0%, 50% and 100% |
| Energy usage | Cumulative kWh, compatible with the Energy dashboard |
| Error status | Current fault description and code |
| Synchronize clock | Uses the time and timezone configured in Home Assistant |

Version 2 keeps everyday controls on the device page and diagnostic tools disabled
by default. Existing pairing credentials, entity identities and saved tariff data
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
3. Submit and wait for completion. Home Assistant synchronizes the heater clock,
   uploads the generated schedule and checks each written portion. This can take
   several minutes.
4. **Electricity tariff** displays the configured plan, for example **PSEG 194**.
   Its attributes include the full utility and rate name, savings preference,
   update status and the last successful update time.

To change your savings preference later, use the **Savings preference** dropdown
on the device page. It rebuilds the entire cached schedule and shows a completion
notification. It does not require another tariff lookup or repeat clock setting.
The dropdown becomes available after a tariff has been configured.

The tariff sensor shows **Updating** during an upload and **Update incomplete**
if a write was interrupted or could not be confirmed. Check the connection and
apply the desired tariff again. The integration retains the original schedule
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

**Availability:** 0%, 50% and 100% are the heater's Low, Medium and High categories,
not measured remaining gallons. Other raw codes display Unknown.

**Energy:** the cumulative kWh sensor can be added to the Energy dashboard.
Instantaneous power and historical cloud data are not provided.

**Clock:** tariff setup synchronizes local time automatically. Use **Synchronize
clock** to set it again, including after a timezone or daylight-saving change.
There are no clock writes on startup or during polling. On tested HPS10 firmware,
clock readback can omit minutes: an acknowledged write with matching date/hour
is accepted and recorded as partial readback. Continued ticking and DST behavior,
actual timed heating and countdown expiry still need physical verification.

## Updates and troubleshooting

Update through HACS and restart **Home Assistant Core** to load new Python code.
There is no need to reboot the host or remove and pair the integration again.
Tariff changes and everyday settings take effect without restarting Home Assistant.
Use **⋮ → Reload** for an integration reconnect; reload does not load newly
downloaded Python modules.

If the heater is unavailable, enable its Bluetooth, check adapter/proxy range
and close any other app using the connection. Keep the existing pairing identifier.

For a diagnostic capture, enable **Inspect extended registers** or **Read stored
tariff schedule** under the device's disabled entities. Wait for the **AO Smith
diagnostic read finished** notification before downloading diagnostics. It reports
completion and unread/error counts. An optional Diagnostic read status sensor is
also available. Previously enabled diagnostic buttons remain enabled on upgrade.

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
