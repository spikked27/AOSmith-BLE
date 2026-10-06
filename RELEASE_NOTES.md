# AO Smith Local BLE 2.1.1

Clock maintenance now checks **once per hour at minute 2**, on the first normal
poll at or after :02, instead of every 15 minutes. This gives the heater time
to advance into the new hour before checking its date/hour readback.

Startup and connection-recovery checks remain. Timezone/DST changes and a new
clock-unset fault can trigger an earlier check. A matching clock is left alone,
except for the daily refresh needed when HPS10 readback omits minutes.
Retry limits, saved history and ordinary heater controls are unchanged.

Update through HACS and restart Home Assistant Core once. If collecting an
independent clock-ticking test, finish that capture on **2.0.0** before updating:
automatic correction can conceal whether the heater advances time by itself.
Extra diagnostic entities remain until that hardware testing is complete.
