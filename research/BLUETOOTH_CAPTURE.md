# Capture the official app's clock and tariff traffic

The local integration can now write and independently read the complete tariff
schedule. Its explicit legacy-format clock experiment gets a success ACK but
does not read back the requested minutes. Capture an ordinary official-app
Bluetooth connection and tariff save to identify its actual commands and order.
No factory reset or new pairing enrollment is needed for this investigation.

Before capturing, one read-only check can narrow the issue: following the
20:51 clock trial, read extended registers after 21:02 without setting the
clock again. If 26:3 changes from `0014` to `0015`, the hour is advancing across
the expected boundary even though minutes read as zero. That would support a
masked/partial clock readback; it still would not prove exact minute accuracy.
If unchanged, capture the official app as below to investigate the interface.

1. Temporarily disable the **AO Smith Local BLE** integration entry in Home
   Assistant to release the heater connection. Keep its configuration and pairing.
2. On the Android phone, enable **Developer options** if needed. On Samsung,
   open **Settings → About phone → Software information → Build number** and
   tap it seven times. Return to Settings and open **Developer options**.
3. Enable **Bluetooth HCI snoop log**, then switch phone Bluetooth off and on.
   If the setting offers logging modes, choose the full/enabled mode so payloads
   are included. Do this before connecting the app to the heater.
4. Open the installed AO Smith/iCOMM app and connect to the heater by Bluetooth.
   Note the phone-local time and app version. Then save **Rate 194 / More Hot
   Water** and note the save time. Wait for the app to finish. If it has a visible
   clock-setting action, capture that action too; do not assume such a screen exists.
5. Immediately open **Developer options → Take bug report**, choose a full
   report if offered, and wait for the ready notification. Save the report ZIP.
   A computer alternative is `adb bugreport heater-capture.zip` after enabling
   USB debugging and authorizing the connected computer.
6. Extract `btsnoop_hci.log` from the report if present; its location varies by
   phone. Share that Bluetooth log with the app version and noted action times.
   If absent, the report may contain Bluetooth data in its main text that can
   be extracted with AOSP's `btsnooz.py`. A full bug report also contains unrelated
   phone/app diagnostics, so the Bluetooth file alone is preferable.
7. Turn HCI logging off, close the official app, and re-enable the HA integration.
   Run **Inspect extended registers**, wait for its finished notification, and
   download diagnostics. This gives the post-app register values for comparison.

These logs can contain Bluetooth pairing/authentication material; keep raw logs
out of the public repository. Publish only the specific sanitized command/reply
fixtures needed for the protocol investigation.

## Official Android references

- Developer options and Samsung's Build number path:
  https://developer.android.com/studio/debug/dev-options
- Bluetooth HCI logging, restarting Bluetooth, and `btsnooz.py` extraction:
  https://source.android.com/docs/core/connect/bluetooth/verifying_debugging
- Capturing/exporting a bug report on-device or with ADB:
  https://developer.android.com/studio/debug/bug-report
