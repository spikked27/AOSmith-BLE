## AO Smith Local BLE 1.3.0

Adds **Diagnostic read status** and a persistent completion notification. Wait
for the notification before downloading diagnostics. Extended reads now continue
after optional registers return status 0x40, so the rejected preference candidate
does not prevent later clock reads. Counts distinguish rejected and unread items.

The experimental preference destination changes to **28:75**: the owner's latest
capture reads `0000` there and rejects 28:113. The captured read packets have valid
CRCs; the earlier “checksum rejected” message alone did not identify a bad CRC.
There is no automatic alternate-address fallback.

**Set heater clock (experimental)** sends HA-local time/date using the recovered
app clock format, checks acknowledgement and readback, and records the result.
This is an explicit next-generation trial; clock writes are not automatic at
startup. An unsupported initial read does not prevent the requested trial.

**Configure → Find and apply a tariff** restores the anonymous AO Smith API:
ZIP → utility → plan → preference → upload. It generates five season blocks plus
holiday/preference data, saves the original schedule durably before writes, and
checks each chunk. With a cached tariff, the preference dropdown regenerates the
whole schedule. Without one it remains a single-word experiment. New controls
read the complete stored schedule and restore the original schedule; the latter
backup survives HA restarts. An ambiguous upload stops without replaying writes.

**Integration version** shows the running version, downloaded version, and whether
a restart is needed. Python code updates still require a **Home Assistant restart**;
integration Reload cannot reliably load new code. No host/Unraid reboot is needed.
Settings changes and tariff actions work without restarting HA after installation.

### Try this release

1. Update through HACS and restart Home Assistant. Confirm Integration version is
   **1.3.0**. Keep the existing pairing and close iCOMM.
2. Press **Set heater clock (experimental)**.
3. Enable **Inspect extended registers** and **Read stored tariff schedule** in
   the entity list. Run each separately and wait for its completion notification,
   then download diagnostics. The status includes incomplete/failed results too.
4. Use **Configure → Find and apply a tariff** to select your actual plan. The
   clock option can be disabled if testing the schedule separately. Allow several
   minutes and retain the resulting diagnostics.

The software suite passes 187 tests on HA 2025.12.5, with lint, formatting and
archive checks. New clock/schedule writes have not been tested on the physical
heater. Readback proves stored bytes, not clock ticking, DST handling or schedule
activation. Live API access was unavailable from the development workspace;
lookup is covered with fixtures and will run from your Home Assistant.
