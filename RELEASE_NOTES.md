## AO Smith Local BLE 1.1.1

Correct the HPS10 hot-water availability mapping:

| Raw value | Category | Display |
|---|---|---|
| 10 | High | 100% |
| 5 | Medium | 50% |
| 0 | Low | 0% |

This applies the owner's specified mapping after raw 10 appeared in two valid
Bluetooth responses. It replaces the earlier interpretation based on readings
at different times. Unknown codes still display Unknown. Low availability is
not a heater fault, and these percentages do not measure remaining tank volume.

Update in HACS and restart Home Assistant. No configuration changes or re-pairing
are needed. Existing entity IDs and raw diagnostic values are preserved; historical
readings are not rewritten. Temperature, modes, timers and tariff scope are unchanged.

145 automated tests pass locally, including all three captured availability
frames and their sensor category/display values, plus Ruff and archive checks.
