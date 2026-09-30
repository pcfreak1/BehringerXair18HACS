"""A loopback UDP mixer using python-osc when available as an independent codec."""

from __future__ import annotations

import asyncio

from custom_components.behringer_xair.model import STRIPS, send_path
from custom_components.behringer_xair.osc import decode_packet, encode_message


class FakeMixer(asyncio.DatagramProtocol):
    def __init__(self):
        self.values = {path: value for s in STRIPS for path, value in ((s.fader, 0.75), (s.on, 1))}
        self.values.update({send_path(ch, bus): 0.5 for ch in range(1, 17) for bus in range(1, 7)})
        self.model = "XR18"
        self.online = True
        self.ignore_writes = False
        self.drop = set()
        self.received = []
        self.raw = []
        self.subscribers = set()
        self.loaded_slots = []

    async def start(self):
        self.transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
            lambda: self, local_addr=("127.0.0.1", 0)
        )
        self.port = self.transport.get_extra_info("sockname")[1]

    def datagram_received(self, data, peer):
        self.raw.append(data)
        # Cross-check generated packets with a separately maintained OSC implementation.
        try:
            from pythonosc.osc_packet import OscPacket
        except ImportError:
            messages = decode_packet(data)
        else:
            messages = [
                (m.message.address, tuple(m.message.params)) for m in OscPacket(data).messages
            ]
        for path, args in messages:
            self.received.append((path, args, peer))
            if not self.online or path in self.drop:
                continue
            if path == "/xinfo":
                self.transport.sendto(
                    encode_message(path, "127.0.0.1", "Studio", self.model, "1.22"), peer
                )
            elif path == "/xremote":
                self.subscribers.add(peer)
            elif path == "/-snap/load" and args:
                self.loaded_slots.append(args[0])
                self.values["/ch/01/mix/fader"] = 0.25
                self.values["/ch/01/mix/on"] = 0
            elif path in self.values:
                if args and not self.ignore_writes:
                    self.values[path] = args[0]
                self.transport.sendto(encode_message(path, self.values[path]), peer)

    def push(self, path, value):
        self.values[path] = value
        for peer in self.subscribers:
            self.transport.sendto(encode_message(path, value), peer)

    def close(self):
        self.transport.close()
