"""Small, bounded OSC codec for the X Air UDP protocol (no HA dependency)."""

from __future__ import annotations

import math
import struct

type OscValue = int | float | str | bytes
type OscMessage = tuple[str, tuple[OscValue, ...]]


class OscError(ValueError):
    """Invalid or unsupported OSC packet."""


def _string(value: str) -> bytes:
    if "\x00" in value:
        raise OscError("OSC strings cannot contain NUL")
    raw = value.encode("utf-8") + b"\x00"
    return raw + b"\x00" * (-len(raw) % 4)


def encode_message(address: str, *values: OscValue) -> bytes:
    """Encode a request or typed message; booleans use the mixer's integer type."""
    if not address.startswith("/"):
        raise OscError("OSC addresses must start with /")
    tags, payload = ",", b""
    for value in values:
        if isinstance(value, int):
            tags += "i"
            payload += struct.pack(">i", value)
        elif isinstance(value, float):
            if not math.isfinite(value):
                raise OscError("Non-finite OSC number")
            tags += "f"
            payload += struct.pack(">f", value)
        elif isinstance(value, str):
            tags += "s"
            payload += _string(value)
        elif isinstance(value, bytes):
            tags += "b"
            payload += struct.pack(">i", len(value)) + value + b"\x00" * (-len(value) % 4)
        else:
            raise OscError(f"Unsupported OSC type: {type(value).__name__}")
    return _string(address) + _string(tags) + payload


def _read_string(data: bytes, offset: int) -> tuple[str, int]:
    end = data.find(b"\x00", offset)
    if end < 0:
        raise OscError("Unterminated OSC string")
    next_offset = (end + 4) & ~3
    if next_offset > len(data) or any(data[end:next_offset]):
        raise OscError("Invalid OSC string padding")
    return data[offset:end].decode("utf-8"), next_offset


def decode_packet(data: bytes, *, _depth: int = 0) -> list[OscMessage]:
    """Decode messages and immediate bundles, rejecting malformed datagrams."""
    if not data or len(data) % 4 or _depth > 8:
        raise OscError("Invalid OSC packet size or bundle nesting")
    try:
        if data.startswith(b"#bundle\x00"):
            if len(data) < 16:
                raise OscError("Truncated OSC bundle")
            offset, messages = 16, []
            while offset < len(data):
                size = struct.unpack_from(">i", data, offset)[0]
                offset += 4
                if size <= 0 or offset + size > len(data):
                    raise OscError("Invalid OSC bundle element")
                messages.extend(decode_packet(data[offset : offset + size], _depth=_depth + 1))
                offset += size
            return messages
        address, offset = _read_string(data, 0)
        if not address.startswith("/"):
            raise OscError("Invalid OSC address")
        # X Air also accepts and occasionally returns address-only messages.
        if offset == len(data):
            return [(address, ())]
        tags, offset = _read_string(data, offset)
        if not tags.startswith(","):
            raise OscError("Missing OSC type tags")
        values: list[OscValue] = []
        for tag in tags[1:]:
            if tag in ("i", "f"):
                value = struct.unpack_from(">" + tag, data, offset)[0]
                if isinstance(value, float) and not math.isfinite(value):
                    raise OscError("Non-finite OSC number")
                values.append(value)
                offset += 4
            elif tag == "s":
                value, offset = _read_string(data, offset)
                values.append(value)
            elif tag == "b":
                size = struct.unpack_from(">i", data, offset)[0]
                offset += 4
                if size < 0 or offset + size > len(data):
                    raise OscError("Invalid OSC blob")
                values.append(data[offset : offset + size])
                offset += (size + 3) & ~3
            else:
                raise OscError(f"Unsupported OSC tag {tag}")
        if offset != len(data):
            raise OscError("Trailing or missing OSC bytes")
        return [(address, tuple(values))]
    except (struct.error, UnicodeDecodeError) as err:
        raise OscError("Malformed OSC packet") from err
