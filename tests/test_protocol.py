"""Captured wire fixtures, byte-order checks, and corrupt input handling."""

import pytest

from custom_components.aosmith_ble.protocol import (
    FrameBuffer,
    ProtocolError,
    StatusError,
    auth_frame,
    check_status,
    crc,
    decode_temperature,
    encode_temperature,
    frame,
    read_frame,
    read_value,
    validate,
    validate_identifier,
    write_frame,
)

READS = [
    ((11, 0), "BDA0070B000132", "DB02090B0033AB80A0", 0x33AB),
    ((11, 15), "BDA0070B0F0198", "DB02090B0F00048000", 4),
    ((27, 23), "BDA0071B170156", "DB02091B17000580AC", 5),
    ((2, 7), "BDA00702070166", "DB020902070000809C", 0),
]


@pytest.mark.parametrize("register,request_hex,response,value", READS)
def test_captured_reads(register, request_hex, response, value):
    assert read_frame(*register).hex().upper() == request_hex
    assert read_value(bytes.fromhex(response), *register) == value


def test_known_writes_and_temperatures():
    assert write_frame(11, 15, 5).hex().upper() == "BD40080B0F00054A"
    assert write_frame(11, 15, 4).hex().upper() == "BD40080B0F000414"
    assert decode_temperature(0x33AB) == 125.0
    assert encode_temperature(120) == 0x30E4
    assert encode_temperature(125) == 0x33AB
    with pytest.raises(ValueError):
        encode_temperature(float("nan"))


def test_authentication_wire_format():
    # Public synthetic credential: not a user's real enrolled pairing.
    packet = auth_frame(bytes.fromhex("DB4F079C6F80C2"), "HA0000000000000001")
    assert packet.hex() == "bdf119011ae195197ce107fd44918e774d92c599571190f92a"
    assert frame(0xF4).hex().upper() == "BDF40412"
    check_status(bytes.fromhex("DB1F0580D2"))


def test_bad_response_and_wrong_register():
    response = bytes.fromhex(READS[0][2])
    with pytest.raises(ProtocolError):
        validate(response[:-1] + b"\x00")
    with pytest.raises(ProtocolError):
        read_value(response, 11, 15)
    with pytest.raises(ProtocolError):
        validate(response[:-1])


def test_status_error_lowest_bit_wins():
    body = bytes.fromhex("DB020510")
    with pytest.raises(StatusError) as error:
        check_status(body + bytes([crc(body)]))
    assert error.value.code == 0x10
    body = bytes.fromhex("DB020590")
    with pytest.raises(StatusError) as error:
        check_status(body + bytes([crc(body)]))
    assert error.value.code == 0x10


def test_fragmentation_concatenation_and_bad_crc_recovery():
    packet = bytes.fromhex(READS[0][2])
    buffer = FrameBuffer()
    assert buffer.feed(b"garbage" + packet[:4]) == []
    assert buffer.feed(packet[4:] + packet) == [packet, packet]
    corrupt = packet[:-1] + bytes([packet[-1] ^ 1])
    assert buffer.feed(corrupt + packet) == [packet]


@pytest.mark.parametrize("identifier", ["short", "H" * 19, "é" * 18, " " * 18])
def test_identifier_validation(identifier):
    with pytest.raises(ValueError):
        validate_identifier(identifier)
