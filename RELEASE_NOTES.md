## AO Smith Local BLE 2.2.0

Automatic clock setting is removed. The clock is only written when you explicitly
press **Synchronize clock**. Startup, reconnects, polling, tariff uploads and
savings changes leave it untouched. Existing pairing and tariff data are retained.

### DR investigation

Enable **Capture DR status**, **Monitor DR for 3 hours**, **Stop DR monitoring**
and optionally **DR monitoring status** in the device's disabled entities.
Monitoring records timestamped raw registers once per minute and stops after
three hours; the start action supports 1–360 minutes. The latest 400 snapshots
and changes survive restart, but a running session does not automatically resume.
Download integration diagnostics after the transition. Unmapped status words
are research candidates, not a verified active DR1/DR2 readout.

### Branding

Bundled AO Smith light/dark logos work in Home Assistant 2026.3+ and the logo is
included on the HACS detail page. HACS's current downloads-list icon still has
an upstream limitation with bundled custom icons (hacs/integration#5223).

Update through HACS and **restart Home Assistant Core**. Re-pairing is unnecessary.
Enable the monitoring button and start it before the tariff boundary you want to
capture. BLE behavior at the boundary still requires validation on your heater.
