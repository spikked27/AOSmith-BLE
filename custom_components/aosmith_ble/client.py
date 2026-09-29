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

from .const import AVAILABILITY, FAULT, HOT_WATER_PLUS, MODE, NOTIFY_UUID, SETPOINT, WRITE_UUID
from .protocol import (
    FrameBuffer,
    ProtocolError,
    StatusError,
    auth_frame,
    check_status,
    decode_temperature,
    frame,
    read_frame,
    read_words,
    validate_identifier,
    write_frame,
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class HeaterState:
    target_temperature: float
    mode: int
    availability: int
    fault: int
    mode_days: int = 0
    registers: dict[str, int] = field(default_factory=dict)


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
        self.connections = 0
        self.authentications = 0
        self.enrollment_attempted = False
        self.optional_registers = {}
        self.unsupported_registers = set()
        self.extended_capture = None
        self.optional_retry_after = {}
        self.optional_errors = {}

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
            "optional_errors": dict(self.optional_errors),
            "extended_capture": self.extended_capture,
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

    async def _request(self, data: bytes, matcher) -> bytes:
        await asyncio.sleep(self._spacing)
        self._buffer = FrameBuffer()
        future = asyncio.get_running_loop().create_future()
        self._pending, self._matcher = future, matcher
        if data[1] in (0xA0, 0x40):
            self._record("tx", frame=data.hex().upper())
        else:
            self._record("tx_session", opcode=data[1])
        try:
            async with asyncio.timeout(self._timeout):
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
            # A short error ACK has no register echo; never accept a different register.
            return len(packet) == 5 or packet[3:5] == bytes(register)

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
        fault = await self._read(FAULT)
        registers = await self._read_optional(self.optional_registers)
        return HeaterState(
            decode_temperature(temperature),
            mode & 0xFF,
            availability & 0xFF,
            fault,
            mode >> 8,
            registers,
        )

    async def _read_optional(self, registers, *, retry_unsupported=False):
        """Bounded known-register reads; failures never invalidate the core snapshot."""
        values = {}
        self.optional_errors = {}
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
                self.optional_retry_after.pop(register, None)
                self.unsupported_registers.discard(register)
            except StatusError as err:
                self.optional_errors[key] = str(err)
                if err.code == 1:
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
            try:
                await self._ensure_session()
                values = await self._read_optional(registers, retry_unsupported=True)
                self.extended_capture = {
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

    async def set_value(self, register, value: int) -> HeaterState:
        async with self._lock:
            try:
                await self._ensure_session()
                # Read first: renew an expired session before issuing a mutation.
                await self._read(register)
                if register == SETPOINT and (await self._read(MODE) & 0xFF) == 2:
                    raise ProtocolError("Leave Vacation mode before changing the temperature")
                if register == HOT_WATER_PLUS and (await self._read(MODE) & 0xFF) not in (1, 4, 5):
                    raise ProtocolError("Hot Water Plus requires Electric, Hybrid or Heat pump mode")
                await asyncio.sleep(self._spacing)
                self._record("tx", frame=write_frame(*register, value).hex().upper())
                async with asyncio.timeout(self._timeout):
                    await self._client.write_gatt_char(
                        WRITE_UUID,
                        write_frame(*register, value),
                        response=True,
                    )
                # The captured write ACK was not supplied. Success comes from readback.
                for _ in range(3):
                    await asyncio.sleep(self._spacing)
                    if await self._read(register) == value:
                        return await self._snapshot()
                raise ProtocolError("Heater did not confirm the requested setting; write was not repeated")
            except BaseException:
                await self._close()
                raise
