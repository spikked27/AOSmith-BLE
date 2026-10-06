## AO Smith Local BLE 1.3.1

Fixes a reproduced false-success bug: a failed tariff upload could show an error,
then a repeated callback could cache the plan and report success. A confirmed
upload result is now required every time. Selected/cached rate information in
1.3.0 alone does not prove that its schedule reached the heater.

Fixes the blank configuration-menu choices by returning explicit labels, so they
remain readable with stale or missing frontend translations.

Clock and schedule writes now use fresh readback even if their acknowledgement
is missing, without repeating the write. Empty success ACKs no longer count as
register data. Command traffic and actual mismatched clock words remain available
after an extended diagnostic scan. Explicit rejection still stops the operation.

Tariff uploads now use a background task owned by the integration entry. HA
shutdown or integration unload cancels the task, releases the BLE connection,
and records the interrupted phase without repeating any write. The original
schedule backup survives. The options flow reports cancellation instead of
leaving an unhandled task result.

Schedule generation runs off HA's main event loop. Capacity checks happen before
event expansion; the actual tariff response is saved before generation and upload
phases are logged to make a future failure diagnosable.

All **201 tests** pass, including false-success regression, missing/delayed ACKs,
captured tariff comparison, HA shutdown during a partially transmitted write,
backup preservation, cancellation on entry unload and menu-label coverage.
Ruff and release archive checks also pass.

The supplied full backup matches Rate 195 / More Savings in every season byte,
while its separate preference word says More Hot Water. The later Rate 194 /
More Hot Water attempt stopped during the clock trial with zero confirmed
schedule chunks. Clock date/hour changed, but requested minutes read back as
zero; correct timekeeping remains unresolved. The research report includes exact
generated schedules for both actual API responses and all three preferences.

The reported HAOS shutdown itself has **not** been reproduced or attributed to
this integration. The screenshot shows services stopping and Supervisor waiting,
not what initiated shutdown. These fixes address confirmed lifecycle defects;
Core, Supervisor and host logs are still needed to identify the original trigger.

Update through HACS and restart **Home Assistant Core only** to load the patch.
Do not remove the integration or its saved pairing. If an upload was interrupted,
download existing diagnostics and read the stored schedule before repeating it.
To isolate the next Rate 194 / More Hot Water upload from the clock issue, leave
the clock checkbox unchecked. Wait for completion, run **Read stored tariff
schedule**, wait for its finished notification, then download diagnostics.
This verifies schedule storage separately from correct clock/event execution.
