# Protocol notes and verified captures

Service: `69400001-b5a3-f393-e0a9-e50e24dcca99`.
Notify: `69400002-b5a3-f393-e0a9-e50e24dcca99`.
Write with response: `69400003-b5a3-f393-e0a9-e50e24dcca99`.

Initial PIN is six ASCII digits, not hex. Subscribe to notifications, reuse an
enrolled 18-byte ASCII identifier, request a two-byte challenge with `BDF40412`,
compute HMAC-SHA1(key=challenge bytes, message=identifier), and send
`BD F1 19 01 <20-byte digest> <CRC>`. Auth success: `DB1F0580D2`.
Enrollment is the separately confirmed `BD F0 16 <18-byte identifier> <CRC>`.
Never send deletion opcode F3 in this integration. F1's literal 01 follows the
tested app sequence; multi-slot behavior needs validation on additional heaters.

CRC uses the exact 256-entry table in `crc_table.py`, initially zero, updated with
`table[crc XOR byte]`. Table came from APK function 14503; it must not be silently
replaced by a presumed standard CRC implementation.

Single-register read: `BD A0 07 block parameter 01 CRC`.
Two-byte write: `BD 40 08 block parameter value_hi value_lo CRC`.
Verified read responses: `DB 02 09 block parameter value_hi value_lo status CRC`.
Status 80 is success. For session errors, the app uses the lowest set status bit:
01 unknown, 02 timeout, 04 key storage full, 08 key missing, 10 session expired,
20 invalid challenge, 40 bad CRC. Response length and CRC are verified.

| Register (decimal) | Meaning | Verified request | Captured response |
|---|---|---|---|
| 11:0 | Setpoint | BDA0070B000132 | DB02090B0033AB80A0 |
| 11:15 | Mode | BDA0070B0F0198 | DB02090B0F00048000 |
| 27:23 | Availability level | BDA0071B170156 | DB02091B17000580AC |
| 2:7 | Fault register | BDA00702070166 | DB020902070000809C |

Setpoint raw `33AB` = 51.66796875°C = approximately 125°F. Temperature encoding
is Celsius times 256, with big-endian wire bytes. Mode low byte: Electric 1,
Vacation 2, Guest 3, Hybrid 4, Heat Pump 5. Upper byte is mode duration; ordinary
non-duration writes use zero. Version 0.2.0 adds explicit duration writes based on the APK.

Owner confirmed successful switch/restore using `BD40080B0F00054A` (Heat Pump)
and `BD40080B0F000414` (Hybrid). A write-ACK screenshot was not supplied. Therefore
the integration uses post-write register readback as its success criterion, not
an invented write ACK schema. Setpoint writes now have physical-display confirmation through HA.

These captures establish the newer register map on one HPS10-80H45DV. Sustained sessions and HA restart/reconnect have passed on that heater. Multi-slot
pairing, proxy transport and other models remain hardware acceptance items.

Design references:
- https://developers.home-assistant.io/docs/core/bluetooth/api/
- https://developers.home-assistant.io/docs/core/entity/water-heater/
- https://www.hacs.dev/docs/publish/integration/
- https://github.com/Bluetooth-Devices/bleak-retry-connector

The APK itself and personal pairing material are not distributed in this package.

## APK-derived extensions in 0.2.0

iCOMM 14.1.0's next-generation module 1422 (Hermes functions 14694–14723)
contains these additional mappings. This is static-code evidence, not a claim
that every model implements every register.

| Decimal register | Meaning | Encoding / exposure |
|---|---|---|
| 1:43 | Maximum setpoint | Celsius × 256, read only; can lower UI ceiling |
| 11:6 | Remote operating setpoint | Separate setpoint register, read only here |
| 11:15 | Mode and duration | High byte duration, low byte mode 1–5 |
| 11:17 | Vacation remaining days | Low byte, raw sentinel retained |
| 11:18 | Guest remaining days | Low byte |
| 11:19 | Electric remaining days | Low byte |
| 11:20 | Hot Water Plus | 0–3; BEST family only, opt-in |
| 27:3 | Utility override / demand-response pause | Write 0000 or 0001 |
| 27:7–9 | Electric power usage words 2,1,0 | Read-only diagnostic capture, units unknown |
| 27:10–12 | Grid present energy words 2,1,0 | Read-only diagnostic capture, units unknown |
| 27:13–15 | Grid total energy words 2,1,0 | Read-only diagnostic capture, units unknown |
| 27:25 | CTA utility module present | Low byte boolean, read only |
| 28:13 | Advanced load-up | Enabled 00A5; disabled 0000 |
| 28:109 | Utility enrollment device flag | Write 0000 or 0001; not cloud enrollment |

Mode writer function 14699 passes duration to the high-byte encoder. The mode
screen (18689–187xx) offers Electric 1–99 days, Vacation 1–100 with 100 labelled
“On”, and Guest 1–7. The dropdown's value is parsed into the mode duration.
Hot Water Plus constants are 0,1,2,3 in function 15291. Function 14722 writes
advanced-load-up with the A5 magic value from module 1417.

Optional polls never replace a missing value with zero. Unknown-register status
01 is skipped until Inspect/reload; transport/corrupt-read errors abort the batch
and defer the failed register for ten minutes. Core readings already obtained
remain usable. Writes still require exact full-word readback and are never replayed.

## Schedule and tariff research (no writes exposed)

The APK has local season writers for blocks 21–25 (functions 14724–14749).
The serializer `seasonToHex` emits four date bytes then twenty six-byte event
slots: hour, minute, unused byte, day-of-week mask, mode, mode-data. Another path
chunks writes into an initial two-register write and subsequent six-register
writes, then reads parameter 0x3E. Holiday data and time/preference setup are
separate. Commit/checksum behavior and next-generation clock/preference addresses
still require validation. Older-family addresses must not be reused on HPS10.

The app also fetches tariff metadata from GraphQL and energy history from
`getEnergyUseData` (average, dated kWh, lifetimeKwh). A local energy word is not
therefore assumed to equal the cloud lifetime counter. No arbitrary register
write or opaque schedule-upload action is exposed.
