"""Simulated peripheral: error recovery, concurrency, and write validation."""

import asyncio
import hashlib
import hmac
import json

import pytest
from bleak.exc import BleakError

from custom_components.aosmith_ble.client import HeaterClient
from custom_components.aosmith_ble.const import MODE, WRITE_UUID
from custom_components.aosmith_ble.protocol import ProtocolError, crc

IDENTIFIER = "HA0000000000000001"


def reply(opcode, payload=b"", status=0x80):
    body = bytes([0xDB, opcode, len(payload) + 5]) + payload + bytes([status])
    return body + bytes([crc(body)])


class FakePeripheral:
    def __init__(self):
        self.is_connected = True
        self.notify = None
        self.disconnect_callback = None
        self.writes = []
        self.registers = {(11, 0): 0x33AB, (11, 15): 4, (27, 23): 5, (2, 7): 0}
        self.expire_once = False
        self.drop_once = False
        self.apply_write = True
        self.write_then_disconnect = False
        self.delay = 0
        self.active_writes = 0
        self.max_active_writes = 0

    async def connect(self, callback):
        self.is_connected = True
        self.disconnect_callback = callback
        return self

    async def disconnect(self):
        self.is_connected = False
        self.disconnect_callback(self)

    async def start_notify(self, _uuid, callback):
        self.notify = callback

    def send(self, packet):
        self.notify(None, packet[:4])
        self.notify(None, packet[4:])

    async def write_gatt_char(self, uuid, data, response):
        assert uuid == WRITE_UUID and response is True
        self.writes.append(data)
        self.active_writes += 1
        self.max_active_writes = max(self.max_active_writes, self.active_writes)
        try:
            await asyncio.sleep(self.delay)
            if data == b"123456":
                return
            assert crc(data[:-1]) == data[-1]
            opcode = data[1]
            if opcode == 0xF0:
                assert data[3:-1] == IDENTIFIER.encode()
                self.send(reply(0x0F, b"\x01"))
            elif opcode == 0xF4:
                self.send(bytes.fromhex("DB4F079C6F80C2"))
            elif opcode == 0xF1:
                assert (
                    data[4:-1] == hmac.new(bytes.fromhex("9C6F"), IDENTIFIER.encode(), hashlib.sha1).digest()
                )
                self.send(bytes.fromhex("DB1F0580D2"))
            elif opcode == 0xA0:
                if self.drop_once:
                    self.drop_once = False
                    await self.disconnect()
                    return
                if self.expire_once:
                    self.expire_once = False
                    self.send(reply(0x02, status=0x10))
                    return
                register = tuple(data[3:5])
                # An unrelated valid frame must not satisfy the read.
                self.send(reply(0x02, b"\x01\x01\x00\x00"))
                self.send(reply(0x02, data[3:5] + self.registers[register].to_bytes(2, "big")))
            elif opcode == 0x40:
                if self.apply_write:
                    self.registers[tuple(data[3:5])] = int.from_bytes(data[5:7], "big")
                if self.write_then_disconnect:
                    await self.disconnect()
                    raise BleakError("Write outcome unknown")
                self.send(reply(0x04))
            else:
                raise AssertionError(f"Unexpected opcode {opcode:02X}")
        finally:
            self.active_writes -= 1


@pytest.fixture
def peripheral():
    return FakePeripheral()


@pytest.fixture
def client(peripheral):
    return HeaterClient(peripheral.connect, "123456", IDENTIFIER, spacing=0, timeout=0.2)


async def test_authenticated_snapshot(client, peripheral):
    state = await client.read_state()
    assert state.target_temperature == 125
    assert (state.mode, state.availability, state.fault) == (4, 5, 0)
    assert peripheral.writes[0] == b"123456"
    assert client.authentications == 1
    await client.read_state()
    assert client.authentications == 1


async def test_expired_session_reauthenticates_once(client, peripheral):
    await client.read_state()
    peripheral.expire_once = True
    assert (await client.read_state()).mode == 4
    assert client.authentications == 2
    assert not any(p[1] in (0xF0, 0xF3) for p in peripheral.writes if p[0] == 0xBD)


async def test_disconnect_read_retries_and_reauthenticates(client, peripheral):
    await client.read_state()
    peripheral.drop_once = True
    assert (await client.read_state()).mode == 4
    assert client.connections == 2


async def test_write_readback_and_restore(client, peripheral):
    assert (await client.set_value(MODE, 5)).mode == 5
    assert (await client.set_value(MODE, 4)).mode == 4
    assert sum(p[1] == 0x40 for p in peripheral.writes if p[0] == 0xBD) == 2


async def test_unapplied_write_is_not_reported_success_or_repeated(client, peripheral):
    peripheral.apply_write = False
    with pytest.raises(ProtocolError, match="did not confirm"):
        await client.set_value(MODE, 5)
    assert sum(p[1] == 0x40 for p in peripheral.writes if p[0] == 0xBD) == 1


async def test_uncertain_write_is_not_replayed(client, peripheral):
    peripheral.write_then_disconnect = True
    with pytest.raises(BleakError):
        await client.set_value(MODE, 5)
    assert peripheral.registers[MODE] == 5
    assert sum(p[1] == 0x40 for p in peripheral.writes if p[0] == 0xBD) == 1


async def test_parallel_calls_are_serialized(client, peripheral):
    peripheral.delay = 0.001
    await asyncio.gather(client.read_state(), client.set_value(MODE, 5), client.read_state())
    assert peripheral.max_active_writes == 1


async def test_enrollment_only_when_requested_and_diagnostics_redacted(client, peripheral):
    await client.enroll()
    await client.read_state()
    await client.disconnect()
    await client.read_state()
    assert sum(p[1] == 0xF0 for p in peripheral.writes if p[0] == 0xBD) == 1
    diag = json.dumps(client.diagnostics()).lower()
    assert IDENTIFIER.lower() not in diag
    assert IDENTIFIER.encode().hex() not in diag
    assert "123456" not in diag
    assert "9c6f" not in diag
    digest = hmac.new(bytes.fromhex("9C6F"), IDENTIFIER.encode(), hashlib.sha1).hexdigest()
    assert digest not in diag
