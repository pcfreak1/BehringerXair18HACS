"""Exercise the real Home Assistant platforms against a loopback UDP mixer."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("homeassistant")

from homeassistant.config_entries import ConfigEntryState  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.exceptions import HomeAssistantError  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.behringer_xair import api  # noqa: E402
from custom_components.behringer_xair.const import DOMAIN  # noqa: E402


@pytest.fixture(autouse=True)
def short_timeouts(monkeypatch, socket_enabled):
    monkeypatch.setattr(api, "REQUEST_TIMEOUT", 0.05)


@pytest.fixture
async def entry(hass: HomeAssistant, mixer):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Studio",
        unique_id=f"127.0.0.1:{mixer.port}",
        data={"host": "127.0.0.1", "port": mixer.port, "name": "Studio"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    yield entry
    if entry.state == ConfigEntryState.LOADED:
        await hass.config_entries.async_unload(entry.entry_id)


def entity_id(hass, entry, platform, key):
    result = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")
    assert result is not None
    return result


async def test_setup_volume_mute_and_push(hass, entry, mixer):
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(entities) == 68
    volume = entity_id(hass, entry, "number", "ch_01_volume")
    enabled = entity_id(hass, entry, "switch", "ch_01_enabled")
    assert hass.states.get(volume).state == "0.0"
    assert hass.states.get(enabled).state == "on"

    await hass.services.async_call(
        "number", "set_value", {"entity_id": volume, "value": -10}, blocking=True
    )
    assert mixer.values["/ch/01/mix/fader"] == 0.5
    await hass.services.async_call("switch", "turn_off", {"entity_id": enabled}, blocking=True)
    assert mixer.values["/ch/01/mix/on"] == 0
    await hass.services.async_call("switch", "turn_on", {"entity_id": enabled}, blocking=True)
    assert mixer.values["/ch/01/mix/on"] == 1

    mixer.push("/ch/01/mix/fader", 0.25)
    await asyncio.sleep(0.02)
    await hass.async_block_till_done()
    assert hass.states.get(volume).state == "-30.0"


async def test_recall_scene_and_service(hass, entry, mixer):
    scene = entity_id(hass, entry, "scene", "snapshot_01")
    await hass.services.async_call("scene", "turn_on", {"entity_id": scene}, blocking=True)
    assert mixer.loaded_slots == [1]
    assert hass.states.get(entity_id(hass, entry, "number", "ch_01_volume")).state == "-30.0"
    await hass.services.async_call(
        DOMAIN, "recall_snapshot", {"config_entry_id": entry.entry_id, "slot": 64}, blocking=True
    )
    assert mixer.loaded_slots == [1, 64]
    # A scene remains callable; recalling the same snapshot is not suppressed.
    await hass.services.async_call("scene", "turn_on", {"entity_id": scene}, blocking=True)
    assert mixer.loaded_slots == [1, 64, 1]


async def test_connection_loss_recovery_and_command_failure(hass, entry, mixer):
    volume = entity_id(hass, entry, "number", "ch_01_volume")
    mixer.online = False
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(volume).state == "unavailable"
    with pytest.raises(HomeAssistantError):
        await entry.runtime_data.async_set("/ch/01/mix/fader", 0.1)
    mixer.values["/ch/01/mix/fader"] = 0.5
    mixer.online = True
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(volume).state == "-10.0"
    mixer.ignore_writes = True
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "number", "set_value", {"entity_id": volume, "value": 0}, blocking=True
        )
    assert hass.states.get(volume).state == "-10.0"


async def test_only_missing_parameter_unavailable(hass, entry, mixer):
    mixer.drop.add("/ch/01/mix/fader")
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id(hass, entry, "number", "ch_01_volume")).state == "unavailable"
    assert hass.states.get(entity_id(hass, entry, "number", "main_volume")).state == "0.0"


async def test_options_reload_sends_and_named_scenes(hass, entry, mixer):
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"snapshots": "2=Muziek\n64=Spraak", "include_sends": True}
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    send = entity_id(hass, entry, "number", "ch_01_bus_1_volume")
    assert hass.states.get(send).state == "-10.0"
    await hass.services.async_call(
        "number", "set_value", {"entity_id": send, "value": -30}, blocking=True
    )
    assert mixer.values["/ch/01/mix/01/level"] == 0.25
    scene = entity_id(hass, entry, "scene", "snapshot_64")
    assert "Spraak" in hass.states.get(scene).attributes["friendly_name"]
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("scene", DOMAIN, f"{entry.entry_id}_snapshot_01") is None
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        flow["flow_id"], {"snapshots": "", "include_sends": False}
    )
    await hass.async_block_till_done()
    assert registry.async_get(send) is None
    assert registry.async_get(scene) is None
    assert len(er.async_entries_for_config_entry(registry, entry.entry_id)) == 64


async def test_service_rejects_other_entries_and_invalid_slots(hass, entry):
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN, "recall_snapshot", {"config_entry_id": "missing", "slot": 1}, blocking=True
        )
    import voluptuous as vol

    for slot in (0, 65):
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                "recall_snapshot",
                {"config_entry_id": entry.entry_id, "slot": slot},
                blocking=True,
            )


async def test_unload_releases_resources(hass, entry):
    coordinator = entry.runtime_data
    client = coordinator.client
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert client._transport is None
    assert client._keepalive_task is None
    assert coordinator._cancel_refresh is None
    assert not hass.services.has_service(DOMAIN, "recall_snapshot")


async def test_offline_setup_is_retried(hass, mixer):
    mixer.online = False
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "127.0.0.1", "port": mixer.port})
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.SETUP_RETRY
    assert entry.runtime_data.client._transport is None


async def test_config_flow_and_duplicate(hass, mixer):
    data = {"host": "127.0.0.1", "port": mixer.port, "name": "Studio"}
    with patch("custom_components.behringer_xair.async_setup_entry", AsyncMock(return_value=True)):
        flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert flow["type"] == "form"
        result = await hass.config_entries.flow.async_configure(flow["flow_id"], data)
        assert result["type"] == "create_entry"
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=data
        )
        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("model", "online", "error"),
    [("XR18", False, "cannot_connect"), ("X32", True, "unsupported_model")],
)
async def test_config_errors(hass, mixer, model, online, error):
    mixer.model, mixer.online = model, online
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data={"host": "127.0.0.1", "port": mixer.port}
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": error}


async def test_invalid_options_keep_form(hass, entry):
    result = await hass.config_entries.options.async_init(
        entry.entry_id, data={"snapshots": "1\n1", "include_sends": False}
    )
    assert result["type"] == "form"
    assert result["errors"] == {"snapshots": "invalid_snapshots"}


async def test_reconfigure_preserves_entity_identity(hass, entry, mixer):
    old_entity = entity_id(hass, entry, "number", "ch_01_volume")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
        data={"host": "localhost", "port": mixer.port, "name": "Stage"},
    )
    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert entry.data["host"] == "localhost"
    assert entry.title == "Stage"
    assert entity_id(hass, entry, "number", "ch_01_volume") == old_entity


async def test_multiple_mixers_have_independent_state_and_service_lifetime(hass, entry, mixer):
    from .fake_mixer import FakeMixer

    other = FakeMixer()
    await other.start()
    second = MockConfigEntry(
        domain=DOMAIN,
        title="Second",
        unique_id=f"127.0.0.1:{other.port}",
        data={"host": "127.0.0.1", "port": other.port},
    )
    second.add_to_hass(hass)
    try:
        assert await hass.config_entries.async_setup(second.entry_id)
        await hass.async_block_till_done()
        await second.runtime_data.async_set("/lr/mix/fader", 0.25)
        assert other.values["/lr/mix/fader"] == 0.25
        assert mixer.values["/lr/mix/fader"] == 0.75
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert hass.services.has_service(DOMAIN, "recall_snapshot")
        await hass.services.async_call(
            DOMAIN,
            "recall_snapshot",
            {"config_entry_id": second.entry_id, "slot": 2},
            blocking=True,
        )
        assert other.loaded_slots == [2]
        assert mixer.loaded_slots == []
    finally:
        if second.state == ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(second.entry_id)
        other.close()
    assert not hass.services.has_service(DOMAIN, "recall_snapshot")


async def test_reopen_closed_socket(hass, entry, mixer):
    client = entry.runtime_data.client
    await client.async_close()
    await entry.runtime_data.async_refresh()
    assert client.connected
    assert entry.runtime_data.last_update_success
    mixer.push("/ch/01/mix/fader", 0.25)
    await asyncio.sleep(0.02)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id(hass, entry, "number", "ch_01_volume")).state == "-30.0"
