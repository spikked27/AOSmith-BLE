"""Serialized BLE transport and challenge authentication for iCOMM."""

import asyncio
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import monotonic
from typing import Any

from bleak.exc import BleakError

from .const import (
    AVAILABILITY,
    CLOCK,
    ENERGY_PREFERENCE,
    ENERGY_PREFERENCES,
    FAULT,
    HOT_WATER_PLUS,
    INSPECT_REGISTERS,
    MAX_TEMP_F,
    MIN_TEMP_F,
    MODE,
    NOTIFY_UUID,
    SETPOINT,
    TIMED_MODE_REGISTERS,
    WRITE_UUID,
)
from .protocol import (
    FrameBuffer,
    ProtocolError,
    StatusError,
    auth_frame,
    check_status,
    decode_clock,
    decode_temperature,
    encode_clock,
    frame,
    read_frame,
    read_words,
    validate_identifier,
    write_frame,
    write_words_frame,
)
from .schedule import decode_season, season_words, validate_payloads
from .timing import DR_NAMES, decode_dr, schedule_digest

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class HeaterState:
    target_temperature: float
    mode: int
    availability: int
    fault: int
    mode_days: int = 0
    registers: dict[str, int] = field(default_factory=dict)
    availability_word: int | None = None
    availability_read_at: str | None = None
    register_read_at: dict[str, str] = field(default_factory=dict)


class HeaterClient:
    """One connection, one in-flight request; reuse the enrolled identifier.

    Connector receives a disconnect callback and returns a connected Bleak client.
    No key enrollment/deletion fallback and no automatic retries of writes.
    """

    def __init__(
        self,
        connector: Callable[..., Awaitable[Any]],
        pin: str,
        identifier: str,
        *,
        timeout: float = 8.0,
        spacing: float = 0.3,
    ):
        if len(pin) != 6 or not pin.isascii() or not pin.isdigit():
            raise ValueError("PIN must contain six ASCII digits")
        self.identifier = validate_identifier(identifier)
        self.pin = pin
        self._connector = connector
        self._client = None
        self._authenticated = False
        self._notification_session = None
        self._lock = asyncio.Lock()
        self._pending = None
        self._matcher = None
        self._buffer = FrameBuffer()
        self._timeout = timeout
        self._spacing = spacing
        self.events = deque(maxlen=60)
        self.commands = deque(maxlen=20)
        self.connections = 0
        self.authentications = 0
        self.enrollment_attempted = False
        self.optional_registers = {}
        self.unsupported_registers = set()
        self.extended_capture = None
        self.optional_retry_after = {}
        self.optional_errors = {}
        self.clock_operation = None
        self.schedule_operation = None
        self.schedule_capture = None

    def _record(self, event, **details):
        record = {"time": datetime.now(timezone.utc).isoformat(), "event": event, **details}
        self.events.append(record)
        LOGGER.debug("%s", record)

    def diagnostics(self):
        return {
            "connected": bool(self._client and self._client.is_connected),
            "authenticated": self._authenticated,
            "connections": self.connections,
            "authentications": self.authentications,
            "events": list(self.events),
            "commands": list(self.commands),
            "optional_errors": dict(self.optional_errors),
            "extended_capture": self.extended_capture,
            "clock_operation": self.clock_operation,
            "schedule_operation": self.schedule_operation,
            "schedule_capture": self.schedule_capture,
        }

    def _disconnected(self, client):
        if client is not self._client:
            return
        self._authenticated = False
        self._record("disconnected")
        if self._pending and not self._pending.done():
            self._pending.set_exception(BleakError("Heater disconnected"))

    def _notification(self, _sender, data):
        for packet in self._buffer.feed(data):
            # Session traffic can reveal credentials/digests; never log its payload.
            if packet[1] in (0x02, 0x04):
                self._record("rx", frame=packet.hex().upper())
            else:
                self._record("rx_session", opcode=packet[1], status=packet[-2])
            if self._pending and not self._pending.done() and self._matcher and self._matcher(packet):
                self._pending.set_result(packet)

    async def _request(self, data: bytes, matcher, *, timeout=None) -> bytes:
        await asyncio.sleep(self._spacing)
        self._buffer = FrameBuffer()
        future = asyncio.get_running_loop().create_future()
        self._pending, self._matcher = future, matcher
        if data[1] in (0xA0, 0x40):
            self._record("tx", frame=data.hex().upper())
        else:
            self._record("tx_session", opcode=data[1])
        try:
            async with asyncio.timeout(self._timeout if timeout is None else timeout):
                await self._client.write_gatt_char(WRITE_UUID, data, response=True)
                packet = await future
            check_status(packet)
            return packet
        finally:
            self._pending, self._matcher = None, None
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()  # Consume a disconnect error if write itself failed.

    async def _authenticate(self):
        challenge = await self._request(frame(0xF4), lambda p: p[1] == 0x4F)
        await self._request(auth_frame(challenge, self.identifier), lambda p: p[1] == 0x1F)
        self._authenticated = True
        self.authentications += 1
        self._record("authenticated")

    async def _ensure_connection(self):
        if self._client is None or not self._client.is_connected:
            self._authenticated = False
            self._buffer = FrameBuffer()
            self._client = await self._connector(self._disconnected)
            self.connections += 1
            self._record("connected")
            # PIN is six ASCII bytes, NOT hexadecimal and NOT a framed command.
            async with asyncio.timeout(self._timeout):
                await self._client.write_gatt_char(WRITE_UUID, self.pin.encode("ascii"), response=True)
                session_client = self._client
                self._notification_session = session = object()

                def notification(sender, data):
                    if self._notification_session is session:
                        self._notification(sender, data)

                await session_client.start_notify(NOTIFY_UUID, notification)

    async def _ensure_session(self):
        await self._ensure_connection()
        if not self._authenticated:
            await self._authenticate()

    async def enroll(self):
        """Only called following explicit one-time setup confirmation."""
        async with self._lock:
            try:
                await self._ensure_connection()
                self.enrollment_attempted = True
                await self._request(
                    frame(0xF0, self.identifier.encode("ascii")),
                    lambda p: p[1] == 0x0F,
                )
            except BaseException:
                await self._close()
                raise

    async def _close(self):
        client, self._client = self._client, None
        self._authenticated = False
        self._notification_session = None
        self._buffer = FrameBuffer()
        if client is not None and client.is_connected:
            try:
                async with asyncio.timeout(self._timeout):
                    await client.disconnect()
            except (BleakError, TimeoutError):
                pass

    async def disconnect(self):
        async with self._lock:
            await self._close()

    async def _read(self, register):
        return (await self._read_words(register))[0]

    async def _read_words(self, register, count=1):
        block, parameter = register

        def matches(packet):
            if packet[1] != 0x02:
                return False
            # Empty success ACKs (including delayed write ACKs) are not register data.
            if len(packet) == 5:
                return packet[-2] != 0x80
            return packet[3:5] == bytes(register) and (packet[-2] != 0x80 or len(packet) == 7 + count * 2)

        try:
            packet = await self._request(read_frame(block, parameter, count), matches)
        except StatusError as err:
            if err.code not in (0x10, 0x20):
                raise
            self._authenticated = False
            await self._authenticate()
            packet = await self._request(read_frame(block, parameter, count), matches)
        return read_words(packet, block, parameter, count)

    async def _snapshot(self):
        temperature = await self._read(SETPOINT)
        mode = await self._read(MODE)
        availability = await self._read(AVAILABILITY)
        availability_read_at = datetime.now(timezone.utc).isoformat()
        fault = await self._read(FAULT)
        requested = dict(self.optional_registers)
        if mode & 0xFF in TIMED_MODE_REGISTERS:
            key, register = TIMED_MODE_REGISTERS[mode & 0xFF]
            # The active countdown is part of the standard state.
            requested = {key: register, **requested}
        registers = await self._read_optional(requested)
        return HeaterState(
            decode_temperature(temperature),
            mode & 0xFF,
            availability & 0xFF,
            fault,
            mode >> 8,
            registers,
            availability_word=availability,
            availability_read_at=availability_read_at,
            register_read_at=dict(self.optional_read_at),
        )

    async def _read_optional(self, registers, *, retry_unsupported=False):
        """Bounded known-register reads; failures never invalidate the core snapshot."""
        values = {}
        self.optional_errors = {}
        self.optional_read_at = {}
        for key, register in registers.items():
            if register in self.unsupported_registers and not retry_unsupported:
                self.optional_errors[key] = "Unsupported; use Inspect to retry"
                continue
            if not retry_unsupported and self.optional_retry_after.get(register, 0) > monotonic():
                self.optional_errors[key] = "Backing off after read failure; use Inspect to retry"
                continue
            try:
                if key == "energy_wh":
                    # One response avoids mixing words across a low-word rollover.
                    words = await self._read_words(register, 3)
                    if words == (0xFFFF, 0xFFFF, 0xFFFF):
                        raise ProtocolError("Energy counter is unavailable")
                    values[key] = (words[0] << 32) | (words[1] << 16) | words[2]
                else:
                    values[key] = await self._read(register)
                self.optional_read_at[key] = datetime.now(timezone.utc).isoformat()
                self.optional_retry_after.pop(register, None)
                self.unsupported_registers.discard(register)
            except StatusError as err:
                self.optional_errors[key] = str(err)
                if err.code in (1, 0x40):
                    self.unsupported_registers.add(register)
                    continue
                break
            except (BleakError, TimeoutError, ProtocolError) as err:
                self.optional_errors[key] = type(err).__name__
                self.optional_retry_after[register] = monotonic() + 600
                # Stop on transport/corruption so late responses cannot leak into another read.
                await self._close()
                break
        return values

    async def inspect_registers(self, registers):
        """Capture only the caller's named allowlist; never issue writes or enroll keys."""
        async with self._lock:
            started = datetime.now(timezone.utc).isoformat()
            try:
                await self._ensure_session()
                values = await self._read_optional(registers, retry_unsupported=True)
                self.extended_capture = {
                    "started_at": started,
                    "time": datetime.now(timezone.utc).isoformat(),
                    "registers": {
                        key: {
                            "block": reg[0],
                            "parameter": reg[1],
                            "raw": values.get(key),
                            "hex": f"{values[key]:04X}" if key in values else None,
                            "error": self.optional_errors.get(key, "Not read") if key not in values else None,
                        }
                        for key, reg in registers.items()
                    },
                }
                return self.extended_capture
            except BaseException:
                await self._close()
                raise

    async def read_state(self) -> HeaterState:
        async with self._lock:
            for attempt in range(2):
                try:
                    await self._ensure_session()
                    return await self._snapshot()
                except (BleakError, TimeoutError):
                    await self._close()
                    if attempt:
                        raise
                except BaseException:
                    await self._close()
                    raise
        raise ProtocolError("No state received")

    async def inspect_dr_status(self):
        """Read the APK's 26-word status block plus known context; never write registers.

        Only 27:0 is interpreted as DR; other unnamed offsets remain candidates.
        Timestamp every row because a snapshot is a sequence, not an atomic read.
        """
        names = {reg: name for name, reg in INSPECT_REGISTERS.items() if reg != (28, 113)}
        registers = dict.fromkeys([(27, i) for i in range(26)] + list(names))
        result = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "complete": False,
            "active_dr_level": None,
            "registers": {
                f"{block}:{parameter}": {
                    "block": block,
                    "parameter": parameter,
                    "name": names.get((block, parameter), "unmapped_status"),
                    "raw": None,
                    "hex": None,
                    "read_at": None,
                    "error": "Not read",
                }
                for block, parameter in registers
            },
        }
        async with self._lock:
            try:
                await self._ensure_session()
                for block, parameter in registers:
                    row = result["registers"][f"{block}:{parameter}"]
                    try:
                        value = await self._read((block, parameter))
                        row.update(raw=value, hex=f"{value:04X}", error=None)
                    except StatusError as err:
                        row["error"] = str(err)
                        if err.code not in (1, 0x40):
                            raise
                    finally:
                        row["read_at"] = datetime.now(timezone.utc).isoformat()
                result["complete"] = all(row["raw"] is not None for row in result["registers"].values())
            except (BleakError, TimeoutError, ProtocolError) as err:
                result["error"] = type(err).__name__
                await self._close()
            except BaseException:
                await self._close()
                raise
            finally:
                result["time"] = datetime.now(timezone.utc).isoformat()
        result["active_dr_level"] = DR_NAMES.get(decode_dr(result["registers"]["27:0"]["raw"]))
        return result

    async def _write_words_confirmed(self, register, words, *, record=None):
        """One write followed by fresh readback; a missing ACK never triggers another write."""
        words = tuple(words)
        packet = write_words_frame(*register, words)
        detail = {
            "register": list(register),
            "requested_words": list(words),
            "ack_timeout_seconds": self._timeout,
        }
        if record is not None:
            record["last_write"] = detail
        try:
            ack = await self._request(
                packet,
                lambda reply: (
                    reply[1] in (0x02, 0x04)
                    and (len(reply) == 5 or (len(reply) == 7 and reply[3:5] == bytes(register)))
                ),
            )
            detail["ack"] = ack.hex().upper()
        except TimeoutError:
            detail["ack"] = "Not received; checking readback without repeating the write"
            # The heater may still be processing the write. A new session prevents
            # a late reply from being mistaken for the next request's response.
            await self._close()
            await self._ensure_session()
        actual = await self._read_words_recover(register, len(words))
        detail["after"] = list(actual)
        if actual != words:
            raise ProtocolError(f"Readback mismatch at {register[0]}:{register[1]}; write was not repeated")
        return actual

    async def _set_clock(self, local_now):
        operation = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "outcome": "not_sent",
            "register": list(CLOCK),
            "traffic": [],
        }
        self.clock_operation = operation
        self.commands.append(operation)
        try:
            try:
                before = await self._read_words(CLOCK, 2)
                operation["before"] = {"words": list(before), "local_time": decode_clock(before)}
            except StatusError as err:
                # This explicit trial is still sent when the candidate cannot be read.
                operation["before_error"] = str(err)
            local = local_now()
            words = encode_clock(local)
            operation.update(
                {"time": local.isoformat(), "requested_words": list(words), "outcome": "unconfirmed"}
            )
            try:
                after = await self._write_words_confirmed(CLOCK, words, record=operation)
                scope = "full"
            except ProtocolError:
                detail = operation.get("last_write", {})
                after = detail.get("after", [])
                # HPS10 returns a zero minute byte even after acknowledging a clock write.
                # Accept only that observed shape, with a real success ACK and matching date/hour.
                if not (
                    detail.get("ack", "").startswith("DB")
                    and len(after) == 2
                    and after[0] == (words[0] & 0xFF)
                    and after[1] == words[1]
                ):
                    raise
                scope = "date_and_hour"
            operation.update(
                {
                    "outcome": "readback_confirmed" if scope == "full" else "acknowledged",
                    "readback_scope": scope,
                    "minute_verified": scope == "full",
                    "after": list(after),
                    "local_time": decode_clock(after),
                    "rtc_running_verified": False,
                }
            )
            return dict(operation)
        except (BleakError, TimeoutError, ProtocolError, ValueError) as err:
            operation["error"] = (
                str(err) if isinstance(err, (ProtocolError, ValueError)) else type(err).__name__
            )
            raise
        finally:
            if (after := operation.get("last_write", {}).get("after")) is not None:
                operation["after"] = after
                operation["local_time"] = decode_clock(after)
            operation["traffic"][:] = [e for e in self.events if e["time"] >= operation["started_at"]]

    async def read_clock(self):
        """Read both calendar words together without changing device settings."""
        async with self._lock:
            try:
                await self._ensure_session()
                return await self._read_words(CLOCK, 2)
            except BaseException:
                await self._close()
                raise

    async def set_clock(self, local_now):
        async with self._lock:
            try:
                await self._ensure_session()
                await self._read(MODE)  # Renew a stale session before the trial.
                return await self._set_clock(local_now)
            except BaseException:
                await self._close()
                raise

    async def _read_words_recover(self, register, count=1):
        """Retry a read once on a fresh session; never resend its preceding write."""
        try:
            return await self._read_words(register, count)
        except (BleakError, TimeoutError) as err:
            self._record("read_retry", register=list(register), error=type(err).__name__)
            await self._close()
            await self._ensure_session()
            return await self._read_words(register, count)

    async def _read_region(self, block, parameter, count):
        words = []
        for offset in range(0, count, 6):
            words.extend(await self._read_words_recover((block, parameter + offset), min(6, count - offset)))
        return words

    async def _capture_schedule(self):
        result = {"time": datetime.now(timezone.utc).isoformat(), "seasons": [], "errors": {}}
        self.schedule_capture = result
        for block in range(21, 26):
            try:
                words = await self._read_region(block, 0, 62)
                value = b"".join(word.to_bytes(2, "big") for word in words).hex().upper()
                result["seasons"].append({"block": block, "value": value, "decoded": decode_season(value)})
            except StatusError as err:
                if err.code not in (1, 0x40):
                    raise
                result["errors"][str(block)] = str(err)
        try:
            words = await self._read_region(28, 50, 29)
            result["extra"] = {"block": 28, "parameter": 50, "words": words}
        except StatusError as err:
            if err.code not in (1, 0x40):
                raise
            result["errors"]["28:50–78"] = str(err)
        result["complete"] = not result["errors"] and len(result["seasons"]) == 5
        return result

    async def inspect_schedule(self):
        async with self._lock:
            try:
                await self._ensure_session()
                return await self._capture_schedule()
            except BaseException:
                await self._close()
                raise

    async def apply_schedule(self, schedule, save_original, *, restoring=False):
        validate_payloads(schedule)
        async with self._lock:
            operation = {
                "time": datetime.now(timezone.utc).isoformat(),
                "outcome": "not_sent",
                "experimental": True,
                "restoring": restoring,
                "confirmed_chunks": 0,
                "activation_verified": False,
                "preference": schedule.get("preference"),
                "phase": "reading_original",
                "traffic": [],
            }
            self.schedule_operation = operation
            self.commands.append(operation)
            try:
                LOGGER.info("Tariff upload: reading the original schedule")
                await self._ensure_session()
                original = await self._capture_schedule()
                if not original["complete"]:
                    raise ProtocolError(
                        "Could not read the full existing schedule; see schedule_capture in diagnostics"
                    )
                operation["phase"] = "saving_original"
                await save_original(original)
                if schedule_digest(original) == schedule_digest(schedule):
                    operation.update(
                        outcome="readback_confirmed", phase="already_current", already_current=True
                    )
                    LOGGER.info("Tariff already matches all stored bytes; no writes needed")
                    return dict(operation)
                operation["outcome"] = "partial_or_unconfirmed"
                operation["phase"] = "writing_holidays"
                LOGGER.info("Tariff upload: writing holiday and preference data")
                extra = schedule["extra"]
                # Holiday rules and preference/threshold/lead-time data first.
                for offset in range(0, 29, 6):
                    register = (28, 50 + offset)
                    operation["last_register"] = list(register)
                    await self._write_words_confirmed(
                        register, extra["words"][offset : offset + 6], record=operation
                    )
                    operation["confirmed_chunks"] += 1
                for block in schedule["seasons"]:
                    operation["phase"] = f"writing_season_{block['block']}"
                    LOGGER.info("Tariff upload: writing season block %s", block["block"])
                    words = season_words(block)
                    # Header, then all twenty event slots. Include the app builder's omitted tail.
                    for start, count in [(0, 2)] + [(i, 6) for i in range(2, 62, 6)]:
                        register = (block["block"], start)
                        operation["last_register"] = list(register)
                        await self._write_words_confirmed(
                            register, words[start : start + count], record=operation
                        )
                        operation["confirmed_chunks"] += 1
                    checksum = (await self._read_words_recover((block["block"], 62)))[0]
                    operation.setdefault("season_check_words", {})[str(block["block"])] = checksum
                operation["outcome"] = "readback_confirmed"
                operation["phase"] = "complete"
                LOGGER.info("Tariff upload complete: %s chunks confirmed", operation["confirmed_chunks"])
                return dict(operation)
            except asyncio.CancelledError:
                operation["interrupted"] = True
                operation["error"] = "Upload cancelled; no automatic write replay"
                LOGGER.warning("Tariff upload cancelled during %s", operation["phase"])
                await self._close()
                raise
            except (BleakError, TimeoutError, ProtocolError, ValueError) as err:
                operation["error"] = (
                    str(err) if isinstance(err, (ProtocolError, ValueError)) else type(err).__name__
                )
                await self._close()
                raise
            except BaseException:
                await self._close()
                raise

            finally:
                operation["traffic"][:] = [e for e in self.events if e["time"] >= operation["time"]]

    async def test_energy_preference(self, value: int, save_original, *, restoring=False):
        """Try the readable contiguous candidate; one write, no address fallback.

        save_original is awaited before transmission so the pre-test value is
        durable even after a restart or an ambiguous write result. Readback is
        evidence of stored bytes, not evidence of schedule/controller behavior.
        """
        if type(value) is not int or value not in ENERGY_PREFERENCES.values():
            raise ValueError("Invalid energy preference word")
        async with self._lock:
            command = {
                "time": datetime.now(timezone.utc).isoformat(),
                "register": list(ENERGY_PREFERENCE),
                "value": value,
                "experimental": True,
                "restoring": restoring,
                "outcome": "not_sent",
                "behavior_verified": False,
                "traffic": [],
            }
            self.commands.append(command)
            try:
                await self._ensure_session()
                before = await self._read(ENERGY_PREFERENCE)
                command["before"] = before
                if before not in ENERGY_PREFERENCES.values():
                    raise ProtocolError("Candidate returned an unexpected word; no write sent")
                await save_original(before)
                if before == value:
                    command["outcome"] = "already_matches"
                    command["after"] = before
                    return dict(command)
                await asyncio.sleep(self._spacing)
                packet = write_frame(*ENERGY_PREFERENCE, value)
                command["outcome"] = "unconfirmed"
                self._record("tx", frame=packet.hex().upper())
                async with asyncio.timeout(self._timeout):
                    await self._client.write_gatt_char(WRITE_UUID, packet, response=True)
                for _ in range(3):
                    actual = await self._read(ENERGY_PREFERENCE)
                    command["after"] = actual
                    if actual == value:
                        command["outcome"] = "readback_confirmed"
                        return dict(command)
                raise ProtocolError("Preference readback did not match; write was not repeated")
            except (BleakError, TimeoutError, ProtocolError) as err:
                command["error"] = str(err) if isinstance(err, ProtocolError) else type(err).__name__
                await self._close()
                raise
            except BaseException:
                await self._close()
                raise
            finally:
                command["traffic"][:] = [e for e in self.events if e["time"] >= command["time"]]

    async def set_value(self, register, value: int, *, expected_mode=None) -> HeaterState:
        async with self._lock:
            command = {
                "time": datetime.now(timezone.utc).isoformat(),
                "register": list(register),
                "value": value,
                "expected_mode": expected_mode,
                "outcome": "not_sent",
            }
            self.commands.append(command)
            try:
                await self._ensure_session()
                # Read first: renew an expired session before issuing a mutation.
                current = await self._read(register)
                if expected_mode is not None:
                    live_mode = current if register == MODE else await self._read(MODE)
                    if (live_mode & 0xFF) != expected_mode:
                        raise ProtocolError("Mode changed on the heater; refresh before setting its duration")
                if register == SETPOINT:
                    if (await self._read(MODE) & 0xFF) == 2:
                        raise ProtocolError("Leave Vacation mode before changing the temperature")
                    if not MIN_TEMP_F <= decode_temperature(value) <= MAX_TEMP_F:
                        raise ProtocolError(f"Temperature must be within {MIN_TEMP_F}–{MAX_TEMP_F} °F")
                if register == HOT_WATER_PLUS and (await self._read(MODE) & 0xFF) not in (1, 4, 5):
                    raise ProtocolError("Hot Water Plus requires Electric, Hybrid or Heat pump mode")
                await asyncio.sleep(self._spacing)
                self._record("tx", frame=write_frame(*register, value).hex().upper())
                command["outcome"] = "unconfirmed"
                async with asyncio.timeout(self._timeout):
                    await self._client.write_gatt_char(
                        WRITE_UUID,
                        write_frame(*register, value),
                        response=True,
                    )
                # The captured write ACK was not supplied. Success comes from readback.
                for _ in range(3):
                    await asyncio.sleep(self._spacing)
                    actual = await self._read(register)
                    confirmed = actual == value
                    # Accept a mode-only readback only when its separate,
                    # app-defined countdown register also confirms the duration.
                    if not confirmed and register == MODE and value >> 8 and actual == (value & 0xFF):
                        timer = TIMED_MODE_REGISTERS.get(value & 0xFF)
                        if timer is not None:
                            confirmed = (await self._read(timer[1]) & 0xFF) == value >> 8
                    if confirmed:
                        command["outcome"] = "confirmed"
                        state = await self._snapshot()
                        command["refresh"] = "ok"
                        return state
                raise ProtocolError("Heater did not confirm the requested setting; write was not repeated")
            except (BleakError, TimeoutError, ProtocolError) as err:
                # Backend exception text can contain Bluetooth addresses.
                command["error"] = str(err) if isinstance(err, ProtocolError) else type(err).__name__
                await self._close()
                raise
            except BaseException:
                await self._close()
                raise
