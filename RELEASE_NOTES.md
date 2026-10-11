## AO Smith Local BLE 3.0.3

Fixes false overnight clock-desync alerts and unnecessary automatic clock writes.

The owner's October 8–11 history showed normal tariff transitions within a minute
of schedule, but Load up began at varying times after its programmed 03:00 start.
That start is no longer used as proof of clock timing.

- Load-up starts cannot trigger a desync alert, write the clock or clear an alert.
- The following tariff check works from either a stable Baseline/preceding DR level
  or Load up. For PSEG 195 / More Savings in October, the morning check is at 06:00.
- Genuine missed tariff transitions still report desync and can receive one bounded
  automatic correction after the complete stored schedule is verified.
- Existing grace periods, freshness/utility/mode guards, correction limits and
  event history remain. No diagnostic entities are added.

Update in HACS and **restart Home Assistant Core**. No tariff reapplication,
re-pairing or heater power cycle is needed. Automatic clock correction can remain
enabled; if you temporarily switched it off, you can re-enable it after restarting.
Historical alerts remain in history. An existing active alert clears only after a
later eligible tariff transition is observed on time.

The programmed tariff and load-up schedule are unchanged. The fix has automated
regression coverage; post-update behavior still needs observation on the heater.
