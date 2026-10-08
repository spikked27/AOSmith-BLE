## AO Smith Local BLE 3.0.0

A public release with transition-based clock verification and a clean device page.

- **Clock synchronization** watches the selected tariff's live DR transitions.
  A missed transition raises **Clock desync detected** and a notification, with
  persistent event count and timestamps.
- **Automatic clock correction**, enabled by default, permits one correction only
  after the complete stored tariff matches and fresh conditions remain eligible.
  Three minutes of grace plus repeated readings protect against normal delay.
  One attempt per unresolved episode, at most once per 24 hours; limits survive
  restart and failures. A later on-time transition must verify the result.
- **Active demand response** shows Baseline, DR1, DR2, DR3 or Load up. The owner
  capture confirms DR1 → Baseline near the 22:00 boundary; other labels follow the
  app's encoding. Verification currently requires Hybrid mode and pauses for
  overrides, missing reads, calendar ambiguity or changed settings.
- **Hot water level** displays Low / Medium / High. The old 0% meant Low, not zero
  usable gallons. Its numeric entity is retained as an availability index for
  existing automations and disabled by default on new installations.
- Remove development diagnostic buttons and status entities, including previously
  enabled ones. Detailed evidence remains in **Download diagnostics**; read-only
  diagnostic actions replace the buttons. Normal controls and manual Synchronize
  clock remain available.
- Preserve pairing, applied tariffs, backups and history. Bundled Home Assistant
  logos and the README/HACS detail-page logo remain included.

Update through HACS and **restart Home Assistant Core**. Re-pairing is unnecessary.
Automations that used removed diagnostic buttons should use the corresponding
`aosmith_ble` diagnostic actions instead. Automatic correction can be switched off
while keeping desync detection.

A missed transition indicates a timing/execution problem; it does not prove the
clock alone caused it. Hardware evidence covers one HPS10-80H45DV on firmware 6.4.
Automatic correction is software-tested, including recorded transition replay;
its recovery effect still needs a future live missed-transition observation.
See VALIDATION.md for the evidence and remaining model/firmware limitations.
