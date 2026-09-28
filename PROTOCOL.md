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
non-duration writes use zero. Vacation/Guest writes are excluded initially.

Owner confirmed successful switch/restore using `BD40080B0F00054A` (Heat Pump)
and `BD40080B0F000414` (Hybrid). A write-ACK screenshot was not supplied. Therefore
the integration uses post-write register readback as its success criterion, not
an invented write ACK schema. Setpoint writes remain opt-in pending hardware testing.

These captures establish the newer register map on one HPS10-80H45DV. Automatic
reconnection, sustained sessions, multi-slot pairing, and other models remain
hardware acceptance items, even when simulation tests pass.

Design references:
- https://developers.home-assistant.io/docs/core/bluetooth/api/
- https://developers.home-assistant.io/docs/core/entity/water-heater/
- https://www.hacs.dev/docs/publish/integration/
- https://github.com/Bluetooth-Devices/bleak-retry-connector

The APK itself and personal pairing material are not distributed in this package.
