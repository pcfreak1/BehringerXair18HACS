import asyncio

import pytest

from custom_components.behringer_xair import api
from custom_components.behringer_xair.api import UnsupportedMixer, XAirClient, XAirError
from custom_components.behringer_xair.osc import encode_message


@pytest.fixture
async def client(mixer, monkeypatch):
    monkeypatch.setattr(api, "REQUEST_TIMEOUT", 0.05)
    device = XAirClient("127.0.0.1", mixer.port)
    await device.async_connect()
    device.start_updates(["/ch/01/mix/fader", "/ch/01/mix/on", "/lr/mix/fader"])
    await device.async_refresh()
    yield device
    await device.async_close()


async def test_shared_socket_types_and_readback(client, mixer):
    assert client.info.model == "XR18"
    await client.async_set("/ch/01/mix/fader", 0.5)
    await client.async_set("/ch/01/mix/on", 0)
    assert client.values["/ch/01/mix/fader"] == 0.5
    assert type(mixer.values["/ch/01/mix/fader"]) is float
    assert type(mixer.values["/ch/01/mix/on"]) is int
    assert len({peer for _, _, peer in mixer.received}) == 1


async def test_external_updates_and_bad_packets(client, mixer):
    event = asyncio.Event()
    client.on_update = event.set
    mixer.push("/ch/01/mix/fader", 0.25)
    await asyncio.wait_for(event.wait(), 1)
    assert client.values["/ch/01/mix/fader"] == 0.25
    client.receive(b"bad")
    client.receive(encode_message("/ch/01/mix/fader", "invalid"))
    client.receive(encode_message("/ch/01/mix/on", 4))
    client.receive(encode_message("/irrelevant", 123))
    assert client.values["/ch/01/mix/fader"] == 0.25
    assert client.values["/ch/01/mix/on"] == 1
    assert "/irrelevant" not in client.values


async def test_offline_then_recovery(client, mixer):
    mixer.online = False
    with pytest.raises(XAirError):
        await client.async_get_info()
    assert client._waiters == {}
    mixer.online = True
    assert (await client.async_get_info()).model == "XR18"


async def test_unconfirmed_write_is_error(client, mixer):
    mixer.ignore_writes = True
    with pytest.raises(XAirError, match="confirm"):
        await client.async_set("/ch/01/mix/fader", 0.1)
    assert client.values["/ch/01/mix/fader"] == 0.75


async def test_missing_control_is_removed(client, mixer):
    mixer.drop.add("/ch/01/mix/fader")
    values = await client.async_refresh()
    assert "/ch/01/mix/fader" not in values
    assert values["/lr/mix/fader"] == 0.75


async def test_snapshot_once_and_refresh(client, mixer):
    await client.async_recall_snapshot(64)
    await client.async_refresh()
    assert mixer.loaded_slots == [64]
    assert client.values["/ch/01/mix/on"] == 0
    assert client.values["/ch/01/mix/fader"] == 0.25
    for slot in (0, 65, 1.5, True):
        with pytest.raises(ValueError):
            await client.async_recall_snapshot(slot)


async def test_unsupported_device_releases_socket(mixer):
    mixer.model = "X32"
    device = XAirClient("127.0.0.1", mixer.port)
    with pytest.raises(UnsupportedMixer):
        await device.async_connect()
    assert device._transport is None


async def test_close_cancels_pending_request(client, mixer):
    mixer.online = False
    task = asyncio.create_task(client.async_request("/xinfo"))
    await asyncio.sleep(0)
    await client.async_close()
    with pytest.raises(XAirError):
        await task
    assert client._waiters == {}
    assert client._keepalive_task is None


async def test_keepalive_renewal(mixer, monkeypatch):
    monkeypatch.setattr(api, "KEEPALIVE_INTERVAL", 0.02)
    device = XAirClient("127.0.0.1", mixer.port)
    await device.async_connect()
    try:
        device.start_updates([])
        await asyncio.sleep(0.075)
        assert sum(path == "/xremote" for path, _, _ in mixer.received) >= 3
    finally:
        await device.async_close()


async def test_invalid_controls_do_not_send(client, mixer):
    before = len(mixer.received)
    for path, value in [
        ("/ch/01/mix/on", 0.0),
        ("/ch/01/mix/fader", 1),
        ("/ch/01/mix/fader", float("nan")),
    ]:
        with pytest.raises(ValueError):
            await client.async_set(path, value)
    with pytest.raises(XAirError):
        await client.async_set("/other", 0.0)
    assert len(mixer.received) == before
