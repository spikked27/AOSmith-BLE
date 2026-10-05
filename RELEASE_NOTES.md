## AO Smith Local BLE 1.1.2

This diagnostic update prepares energy-usage preference support. **It does not
add an energy-preference control yet.** The APK's Bluetooth and Wi-Fi paths use
different addresses for newer heaters, so a hardware comparison is required.

The existing disabled-by-default **Inspect extended registers** button now reads
both candidate addresses and includes their raw values or errors in diagnostics.
There are no new entities, configuration options, automatic polls or writes.

Update in HACS and restart Home Assistant. For the next check, inspect/download
diagnostics before and after changing the preference in the official iCOMM app,
and report both option labels. See the README for connection instructions.

149 tests, Ruff checks and archive validation pass locally. These checks verify
read-only capture and error handling, not the candidates' hardware meaning.
