## AO Smith Local BLE 3.0.2

Fixes the tariff-setting failure that appeared as **HomeAssistantError**.

- Give write acknowledgements the full eight-second response window. The captured
  heater ACK arrived after 4.3 seconds, exceeding the old two-second shortcut.
- Reconnect for readback after a missing acknowledgement. Retry a lost read once
  on a fresh connection; never resend a write automatically.
- Read all 678 tariff bytes first. If the selected schedule already matches,
  confirm it without rewriting. A successful complete read also clears an earlier
  incomplete-update status and allows clock verification to resume.
- Show a useful failure explanation with the stage and whether writes were sent.
  Detailed evidence stays in Download diagnostics; no diagnostic entities added.

Update in HACS and **restart Home Assistant Core**, then apply the desired tariff
once more. The owner's latest captured PSEG 195 / More Savings schedule already
matched, so that selection should now finish after read-only verification, provided
the full read succeeds. Other savings choices still upload their complete schedule.
No re-pairing or heater power cycle is required by this fix.

Includes all 3.0 clock-verification and hot-water category improvements.
