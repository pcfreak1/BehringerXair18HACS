"""Asynchronous OSC transport using one UDP socket for requests and replies."""

from __future__ import annotations

import asyncio
import logging
import socket
from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass

from .osc import OscError, OscValue, decode_packet, encode_message

_LOGGER = logging.getLogger(__name__)
REQUEST_TIMEOUT = 1.0
KEEPALIVE_INTERVAL = 5.0


class XAirError(Exception):
    """The mixer could not complete an operation."""


class UnsupportedMixer(XAirError):
    """This integration only supports the XR18 and X18 address layout."""


@dataclass(frozen=True)
class MixerInfo:
    """Information returned by /xinfo (there is no serial number here)."""

    host: str
    name: str
    model: str
    firmware: str


class _Protocol(asyncio.DatagramProtocol):
    def __init__(self, client: XAirClient) -> None:
        self.client = client

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        self.client.receive(data)

    def error_received(self, exc: Exception) -> None:
        # A transient ICMP error must not stop the subscription task.
        _LOGGER.debug("X Air UDP error: %s", exc)

    def connection_lost(self, exc: Exception | None) -> None:
        for waiters in self.client._waiters.values():
            for waiter in waiters:
                if not waiter.done():
                    waiter.set_exception(XAirError("UDP socket closed"))


class XAirClient:
    """A connected UDP socket filters out replies from other endpoints."""

    def __init__(self, host: str, port: int = 10024) -> None:
        self.host = host
        self.port = port
        self.info: MixerInfo | None = None
        self.values: dict[str, OscValue] = {}
        self.on_update: Callable[[], None] | None = None
        self._transport: asyncio.DatagramTransport | None = None
        self._waiters: dict[str, list[asyncio.Future]] = {}
        self._write_locks: dict[str, asyncio.Lock] = {}
        self._paths: set[str] = set()
        self._keepalive_task: asyncio.Task | None = None
        self._refresh_lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        """Whether the local socket is open (not a claim of mixer reachability)."""
        return self._transport is not None and not self._transport.is_closing()

    async def async_connect(self) -> MixerInfo:
        """Open the socket and verify the model, releasing it on any failure."""
        try:
            transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
                lambda: _Protocol(self), remote_addr=(self.host, self.port), family=socket.AF_INET
            )
            self._transport = transport
            return await self.async_get_info()
        except BaseException:
            await self.async_close()
            raise

    async def async_get_info(self) -> MixerInfo:
        values = await self.async_request("/xinfo", attempts=3)
        if len(values) < 4 or not all(isinstance(v, str) for v in values[:4]):
            raise XAirError("Invalid /xinfo response")
        if values[2].upper() not in {"XR18", "X18"}:
            raise UnsupportedMixer(f"Unsupported model: {values[2]}")
        assert self._transport is not None
        peer = self._transport.get_extra_info("peername")[0]
        self.info = MixerInfo(peer, values[1], values[2], values[3])
        return self.info

    def start_updates(self, paths: Iterable[str]) -> None:
        """Subscribe before reading initial state to avoid an update gap."""
        self._paths = set(paths)
        self.send("/xremote")
        if self._keepalive_task is None:
            self._keepalive_task = asyncio.create_task(self._keepalive())

    async def _keepalive(self) -> None:
        while True:
            await asyncio.sleep(KEEPALIVE_INTERVAL)
            with suppress(XAirError):
                self.send("/xremote")

    def send(self, address: str, *values: OscValue) -> None:
        if self._transport is None or self._transport.is_closing():
            raise XAirError("Mixer is disconnected")
        try:
            self._transport.sendto(encode_message(address, *values))
        except OSError as err:
            raise XAirError("Could not send to mixer") from err

    def receive(self, data: bytes) -> None:
        """Process valid replies; unknown broadcast addresses never grow the cache."""
        try:
            messages = decode_packet(data)
        except OscError:
            _LOGGER.debug("Ignoring malformed X Air datagram")
            return
        changed = False
        for address, values in messages:
            if not values:
                continue
            if address in self._paths:
                value = values[0]
                # Only normalized levels and integer enable flags are tracked.
                if address.endswith("/on"):
                    valid = type(value) is int and value in (0, 1)
                else:
                    valid = type(value) in (float, int) and 0 <= value <= 1
                if not valid:
                    continue
                if self.values.get(address) != value:
                    self.values[address] = value
                    changed = True
            for future in tuple(self._waiters.get(address, ())):
                if not future.done():
                    future.set_result(values)
        if changed and self.on_update:
            self.on_update()

    async def async_request(self, address: str, *, attempts: int = 2) -> tuple[OscValue, ...]:
        """Retry reads only; never retry a potentially destructive command."""
        for _ in range(attempts):
            future = asyncio.get_running_loop().create_future()
            self._waiters.setdefault(address, []).append(future)
            try:
                self.send(address)
                async with asyncio.timeout(REQUEST_TIMEOUT):
                    return await future
            except TimeoutError:
                pass
            finally:
                self._waiters[address].remove(future)
                if not self._waiters[address]:
                    del self._waiters[address]
        raise XAirError(f"Mixer did not answer {address}")

    async def async_refresh(self) -> dict[str, OscValue]:
        """Read in small batches; invalidate missing replies instead of retaining stale values."""
        async with self._refresh_lock:
            paths = sorted(self._paths)

            async def read(path: str) -> None:
                try:
                    await self.async_request(path)
                except XAirError:
                    self.values.pop(path, None)

            for start in range(0, len(paths), 8):
                await asyncio.gather(*(read(path) for path in paths[start : start + 8]))
                await asyncio.sleep(0.02)
            return dict(self.values)

    async def async_set(self, address: str, value: float | int) -> None:
        """Write once, then read back the actual value rather than assuming success."""
        if address not in self._paths:
            raise XAirError("Unknown mixer control")
        if address.endswith("/on"):
            if type(value) is not int or value not in (0, 1):
                raise ValueError("Enable state must be integer 0 or 1")
        elif type(value) is not float or not 0 <= value <= 1:
            raise ValueError("Level must be a float between 0 and 1")
        async with self._write_locks.setdefault(address, asyncio.Lock()):
            self.send(address, value)
            await asyncio.sleep(0.04)
            actual = (await self.async_request(address))[0]
            if not isinstance(actual, (int, float)) or abs(actual - value) > 0.002:
                raise XAirError("Mixer did not confirm the requested value")

    async def async_recall_snapshot(self, slot: int) -> None:
        """Recall an internal snapshot once; OSC does not guarantee acknowledgement."""
        if type(slot) is not int or not 1 <= slot <= 64:
            raise ValueError("Snapshot must be an integer from 1 to 64")
        await self.async_get_info()
        self.send("/-snap/load", slot)
        await asyncio.sleep(0.35)

    async def async_close(self) -> None:
        """Stop keepalive and pending requests, then release the socket."""
        self.on_update = None
        if self._keepalive_task is not None:
            self._keepalive_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._keepalive_task
            self._keepalive_task = None
        if self._transport is not None:
            self._transport.close()
            self._transport = None
        for waiters in self._waiters.values():
            for waiter in waiters:
                if not waiter.done():
                    waiter.set_exception(XAirError("Mixer connection closed"))
