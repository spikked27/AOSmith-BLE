"""Pure wire codec. No cloud, device access, or HA dependencies."""

import hashlib
import hmac
import math

from .const import DEFAULT_MAX_TEMP_F, MAX_TEMP_F, MIN_TEMP_F
from .crc_table import CRC_TABLE


class ProtocolError(Exception):
    """A malformed, corrupt, unexpected, or rejected packet."""


class StatusError(ProtocolError):
    """A device rejection (lowest set ACK bit, matching the app)."""

    def __init__(self, status: int):
        self.status = status
        self.code = status & -status
        meaning = {
            1: "unknown command/error",
            2: "pairing timeout",
            4: "pair key storage full",
            8: "pairing identifier not found",
            16: "session expired",
            32: "challenge invalid",
            64: "checksum rejected",
        }.get(self.code, "invalid status")
        super().__init__(f"Heater rejected request: {meaning} (0x{status:02X})")


def crc(data: bytes) -> int:
    value = 0
    for byte in data:
        value = CRC_TABLE[value ^ byte]
    return value


def frame(command: int, payload: bytes = b"") -> bytes:
    body = bytes((0xBD, command, len(payload) + 4)) + payload
    return body + bytes((crc(body),))


def validate(packet: bytes) -> bytes:
    if len(packet) < 5 or packet[0] != 0xDB or packet[2] != len(packet):
        raise ProtocolError("Invalid response framing")
    if crc(packet[:-1]) != packet[-1]:
        raise ProtocolError("Response checksum mismatch")
    return packet


def check_status(packet: bytes) -> None:
    validate(packet)
    if packet[-2] != 0x80:
        raise StatusError(packet[-2])


def read_frame(block: int, parameter: int, count: int = 1) -> bytes:
    if not 1 <= count <= 6 or parameter + count > 256:
        raise ValueError("Read one to six contiguous words")
    return frame(0xA0, bytes((block, parameter, count)))


def write_frame(block: int, parameter: int, value: int) -> bytes:
    return frame(0x40, bytes((block, parameter)) + value.to_bytes(2, "big"))


def read_value(packet: bytes, block: int, parameter: int) -> int:
    return read_words(packet, block, parameter, 1)[0]


def read_words(packet: bytes, block: int, parameter: int, count: int) -> tuple[int, ...]:
    check_status(packet)
    if len(packet) != 7 + count * 2 or packet[1] != 0x02 or packet[3:5] != bytes((block, parameter)):
        raise ProtocolError("Read response does not match requested register")
    return tuple(int.from_bytes(packet[i : i + 2], "big") for i in range(5, len(packet) - 2, 2))


def auth_frame(challenge_packet: bytes, identifier: str) -> bytes:
    check_status(challenge_packet)
    if len(challenge_packet) != 7 or challenge_packet[1] != 0x4F:
        raise ProtocolError("Invalid challenge response")
    digest = hmac.new(challenge_packet[3:5], identifier.encode("ascii"), hashlib.sha1).digest()
    # 01 is the selector in the verified app sequence, not a guessed key slot.
    return frame(0xF1, b"\x01" + digest)


def validate_identifier(identifier: str) -> str:
    if len(identifier) != 18 or not identifier.isascii() or not identifier.isalnum():
        raise ValueError("Pairing identifier must contain exactly 18 ASCII letters/digits")
    return identifier


def decode_temperature(raw: int) -> float:
    return round(raw / 256 * 1.8 + 32, 1)


def temperature_limit(raw: int | None, current: float) -> float:
    """Honor a reported maximum; missing data never grants a temperature increase."""
    if raw is not None:
        maximum = decode_temperature(raw)
        if MIN_TEMP_F <= maximum <= 180:
            return min(MAX_TEMP_F, maximum)
    return min(DEFAULT_MAX_TEMP_F, max(MIN_TEMP_F, current))


def decode_availability(raw: int, scale: str) -> int | None:
    """Apply only the explicitly selected scale; never infer one from a single byte."""
    if type(raw) is not int:
        return None
    if scale == "hps10_observed":
        # HPS10-80H45DV / firmware 6.4 observations, not a universal enum.
        # The Low category's wire value has not been observed; do not guess it.
        return {0: 50, 5: 100}.get(raw)
    return None


def encode_temperature(fahrenheit: float) -> int:
    if not math.isfinite(fahrenheit):
        raise ValueError("Temperature must be finite")
    return math.floor((fahrenheit - 32) / 1.8 * 256 + 0.5)


class FrameBuffer:
    """Accumulate fragmented notifications and extract complete checked frames."""

    def __init__(self):
        self.data = bytearray()

    def feed(self, data: bytes) -> list[bytes]:
        self.data.extend(data)
        frames = []
        while self.data:
            if self.data[0] != 0xDB:
                del self.data[0]
                continue
            if len(self.data) < 3:
                break
            size = self.data[2]
            if size < 5:
                del self.data[0]
                continue
            if len(self.data) < size:
                break
            packet = bytes(self.data[:size])
            try:
                validate(packet)
            except ProtocolError:
                del self.data[0]
                continue
            del self.data[:size]
            frames.append(packet)
        return frames


def encode_timed_mode(mode: str, days: int) -> int:
    """APK mode high byte is duration; Vacation 100 means continuously on."""
    codes = {"Electric": 1, "Vacation": 2, "Guest": 3}
    maximum = {"Electric": 7, "Vacation": 100, "Guest": 7}
    if mode not in codes or type(days) is not int or not 1 <= days <= maximum[mode]:
        raise ValueError("Use Electric 1–7 days, Vacation 1–100 (100 = on), or Guest 1–7 days")
    return (days << 8) | codes[mode]
