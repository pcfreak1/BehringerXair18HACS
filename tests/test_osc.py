import math
import struct

import pytest

from custom_components.behringer_xair.osc import OscError, decode_packet, encode_message


def test_known_wire_bytes():
    assert encode_message("/xremote") == b"/xremote\x00\x00\x00\x00,\x00\x00\x00"
    assert encode_message("/-snap/load", 1) == b"/-snap/load\x00,i\x00\x00\x00\x00\x00\x01"
    assert encode_message("/ch/01/mix/on", 0).endswith(b",i\x00\x00\x00\x00\x00\x00")
    assert encode_message("/lr/mix/fader", 0.75).endswith(b",f\x00\x00\x3f\x40\x00\x00")


@pytest.mark.parametrize(
    "values", [(), (1, -1), (0.75,), ("héllo", ""), (b"\x01\x02",), (1, "XR18", 0.5)]
)
def test_round_trip(values):
    assert decode_packet(encode_message("/test", *values)) == [("/test", values)]


def test_address_only_and_bundle():
    assert decode_packet(b"/xinfo\x00\x00") == [("/xinfo", ())]
    messages = [encode_message("/a", 1), encode_message("/b", 0.75)]
    packet = b"#bundle\x00" + struct.pack(">Q", 1)
    for message in messages:
        packet += struct.pack(">i", len(message)) + message
    assert decode_packet(packet) == [("/a", (1,)), ("/b", (0.75,))]


@pytest.mark.parametrize(
    "packet",
    [
        b"",
        b"oops",
        b"/aaa",
        b"/a\x00\x00,f\x00\x00",
        b"/a\x00\x00,z\x00\x00",
        b"#bundle\x00",
        b"/a\x00\x00,b\x00\x00\xff\xff\xff\xff",
        b"/a\x00\x00,f\x00\x00\x7f\xc0\x00\x00",
    ],
)
def test_invalid_packets(packet):
    with pytest.raises(OscError):
        decode_packet(packet)


def test_nonfinite_and_nul_rejected():
    for value in (math.nan, math.inf, "a\x00b"):
        with pytest.raises(OscError):
            encode_message("/a", value)


def test_bundle_depth_bounded():
    data = encode_message("/a", 1)
    for _ in range(10):
        data = b"#bundle\x00" + struct.pack(">Qi", 1, len(data)) + data
    with pytest.raises(OscError):
        decode_packet(data)
