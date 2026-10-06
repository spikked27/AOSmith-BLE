# AO Smith Local BLE 2.0.0

A cleaner everyday interface with complete tariff and savings controls.

- **Electricity tariff** shows the configured utility and rate, such as **PSEG 194**.
- **Savings preference** applies More Hot Water, More Savings or Most Savings to
  the complete cached schedule, with progress/completion notifications and durable
  storage of the last confirmed plan. No Internet lookup is needed to change it.
- **Configure** opens tariff setup directly: ZIP, utility, rate and preference.
  Clock synchronization is included automatically.
- **Mode duration** supports Electric, Vacation and Guest; Hot Water Plus appears
  automatically on a heater reporting support.
- Removed public restore buttons and experimental option switches. Diagnostic
  entities are disabled by default; already enabled inspection buttons stay enabled.
- Clock synchronization accepts the observed acknowledged HPS10 zero-minute
  readback when date/hour match. Diagnostics distinguish partial from full readback;
  they do not claim RTC ticking or DST verification.
- Added the standard blue HACS installation button, status badges, streamlined
  setup documentation and issue templates.

The owner-confirmed Rate 194 / More Hot Water upload matches all 678 stored bytes.
The further clock check is independent of this release. Heating behavior and
clock ticking still require physical verification.

Update through HACS, then restart **Home Assistant Core once** to load version 2.
Keep the existing integration and pairing. Normal settings and tariff changes
work without a restart. Upgrading itself sends no clock or tariff writes.
