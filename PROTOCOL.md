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
| 27:7–9 | Electric power usage words 2,1,0 | 48-bit Wh, exposed as kWh |
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

## Schedule and tariff research (no schedule writes exposed)

The APK has local season writers for blocks 21–25 (functions 14724–14749).
The serializer `seasonToHex` emits four date bytes then twenty six-byte event
slots: hour, minute, unused byte, day-of-week mask, mode, mode-data. Another path
chunks writes into an initial two-register write and subsequent six-register
writes, then reads parameter 0x3E. Holiday data and time/preference setup are
separate. Commit/checksum behavior and next-generation clock/preference addresses
still require validation. The two concrete preference candidates and their
conflicting APK paths are documented in RESEARCH.md. Inspect reads 28:75 and
28:113 without interpreting or writing them. Older-family addresses must not be reused on HPS10.

The app also fetches tariff metadata from GraphQL and energy history from
`getEnergyUseData` (average, dated kWh, lifetimeKwh). A local energy word is not
therefore assumed to equal the cloud lifetime counter. No arbitrary register
write or opaque schedule-upload action is exposed.


## Energy and retired tariff functionality

The electrical-use words at 27:7–9 combine MSW first into a 48-bit Wh counter.
Observed words 0000 0005 5944 produce 350532 Wh, consistent with the owner’s
approximately 350 kWh app reading. Normal polling now requests count=3 in one A0
read (response length 13), avoiding separately sampled rollover words. Scaling
is supported by one paired observation; progression/reset behavior still requires physical validation.
The grouped request/reply was subsequently confirmed on hardware. Missing/error/all-FFFF
responses never become a false zero. The grid-energy groups remain undecoded.

The former tariff lookup/cache was removed in development 0.3.2.dev1.
Use iCOMM for tariff setup; this component exposes no schedule programming.
Manual inspection includes candidate clock words 26:3–4 from the older-profile
APK clock writer; their meaning on next-generation heaters remains unverified.
See RESEARCH.md for the clock and schedule findings.


## 0.3.1 availability and clock evidence

The next-generation WATER_AVAILABLE parser in iCOMM module 1422 returns the
low byte of 27:23 unchanged. It does not establish a 0–5 percentage scale. The
public cloud client uses a different numeric convention (`100 - hotWaterStatus`):
https://github.com/bdr99/py-aosmith/blob/8d4eb7f1b75e1898227810ff9d007d8fd3291434/py_aosmith/client.py
Neither path proves that the two fields share a scale. The integration now defaults to the observed HPS10 categories. The speculative 0–5 conversion was removed in 1.0.0; only the observed HPS10
categories remain, and version 1.1.0 makes them the fixed default. Out-of-range bytes never
produce a fabricated percentage; raw bytes remain available for investigation.

The owner’s 0.3.0 captures confirm request BDA0071B0703D8 and response
DB020D1B0700000005594480F0 for the 48-bit energy counter. A credential-free
fixture verifies this exact grouped response. Candidate clock words 26:3 and
26:4 both remain zero at two captures about four minutes apart. A successful
read ACK alone does not confirm register meaning or support for clock writes.


## Duration verification and clock call path

The Vacation/Guest selector follows the current timed mode; outside those modes
it displays Off. Mode entry through HA uses Vacation 7 days or Guest 1 day.
Selecting Off while in either timed mode exits to Hybrid.
The transport rereads 11:15 inside its lock before writing. A differing mode
aborts without mutation. Exact command-word readback still confirms a write;
when 11:15 returns only the requested low-byte mode, its corresponding
remaining-days status (11:17/18/19) must also equal the requested duration.
This second confirmation path is simulated, not yet observed on the owner's
hardware. No unconfirmed write is replayed. Normal polling always reads the active countdown.

The app connection generator #13456 checks `heatPump` before calling
`setEssentialParams` (#13493), which invokes `setClock` (#14611). Bytecode offsets
0x8E–0xAA establish that profile guard. Consequently, the block-26 clock writer
is not established for the next-generation heater. Four zero captures do not
resolve it. See RESEARCH.md; do not reuse the older writer as a generic clock action.


## Consolidated fault decoding and final review

Block 2:7 uses the low byte for the current fault (APK module 1422); the full
word is retained in attributes/diagnostics. Module 1488 selects catalog 1489
for the next-generation profile. Code 0 means no fault reported; 42 means clock
not set. `faults.py` supplies short labels for all byte-sized codes in that
catalog. Its entry 330 cannot fit this parser and is deliberately not aliased to
74. Unknown byte codes remain explicit problems. A failed poll is unavailable,
not a no-fault result. One Error status binary sensor replaces duplicate fault
readings while retaining the existing fault-present unique ID.

Version 1.1.0 removes register 1:43 and current setpoint from the write-ceiling
calculation after the owner observed a shrinking maximum. The fallback had
incorrectly prevented raising temperature after lowering it. Writes use the
documented HPS10 95–150°F range, recheck live Vacation mode, and still require
subsequent setpoint readback. Register 1:43 remains a read-only diagnostic candidate;
no maximum-register override is written.


## HPS10 availability categories — corrected in 1.1.1

The default mapping is raw 0 → Low/0%, 5 → Medium/50%, 10 → High/100%.
Captured frames `DB02091B17000080CA`, `DB02091B17000580AC`, and
`DB02091B17000A8006` validate the wire decoding. The last was observed twice in
the September 28 23:52 EDT capture with successful polling and fault 0.

The owner specified this corrected interpretation after raw 10 appeared. It
supersedes the earlier mapping inferred from non-simultaneous BLE/app readings;
it is not an APK-defined enum. Other values remain unknown. Low availability
is not a heater fault or an empty-tank indication. Raw byte/full word remain in
diagnostics; recorded history is not rewritten.


## Version 1.0.0 limits and Low availability

The integration limits timed Electric to the HPS10 manual's 1–7 days, despite
broader generic app choices. Vacation allows 1–99 or 100 (indefinite); Guest 1–7.
The public action validates these ranges before issuing a write.

The APK's `hexToInt` helper uses `parseInt(value, 16)`; the next-generation
WATER_AVAILABLE path selects the low byte without signed conversion. A signed
8-bit -5 would appear as 251 (0xFB); a signed 16-bit -5 as 65531 (0xFFFB), still
251 after the app's low-byte extraction. Neither has an established Low meaning.
The full raw word is now retained as `state.availability_word` in diagnostics.
No unknown availability code is converted to an error or guessed percentage.

## Experimental preference write (1.2.0)

The explicit opt-in test uses 28:113 (0x1C:0x71), matching the BLE
`sendHolidays → formatExtraData → createHolidayFrames` path. Mapping:
More Hot Water = 1, More Savings = 0, Most Savings = 2. The generic setting-write
allowlist is unchanged; a dedicated method permits only this address and enum.
It reads the original word, waits for a durable backup, sends one write, and
checks up to three readbacks. Same-value requests send no write. It never tries
28:75 or legacy 27:113 as a fallback. This does not demonstrate that firmware
applies the preference or recalculates its already-uploaded schedule.
