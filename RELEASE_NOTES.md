## AO Smith Local BLE 1.2.0

Adds an opt-in **Energy preference (experimental)** dropdown with **More Hot
Water**, **More Savings**, and **Most Savings**. Configure the integration to
show it, then select a preference explicitly. Enabling the feature does not
change any heater setting.

The test uses only iCOMM's BLE candidate address, saves the initial word on disk,
sends one write, and verifies readback. **Restore original energy preference**
uses the saved value even after restart. Unsupported reads, unexpected values,
or failed backup prevent writes; ambiguous writes are not automatically retried.

This is a hardware experiment: readback confirms a stored word, not heating
behavior. The app also recalculates schedule modes from the preference; this
release does not rewrite the schedule, clock, tariffs or other settings.

Update through HACS and **restart Home Assistant**. Enable experimental energy
preference in integration options, try More Hot Water, then download diagnostics.
Check the `transport.commands` result and `energy_preference_original` fields.
See RESEARCH.md for the repeated clock investigation and exact known limitations.
