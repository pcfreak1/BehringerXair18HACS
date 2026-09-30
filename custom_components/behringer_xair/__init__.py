"""Home Assistant integration for Behringer X Air XR18 / X18 mixers."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import CONF_INCLUDE_SENDS, CONF_SNAPSHOTS, DEFAULT_SNAPSHOTS, DOMAIN
from .coordinator import XAirConfigEntry, XAirCoordinator
from .model import parse_snapshots

PLATFORMS = [Platform.NUMBER, Platform.SWITCH, Platform.SCENE]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: XAirConfigEntry) -> bool:
    """Connect and load entities; leave no socket behind on failed setup."""
    coordinator = XAirCoordinator(hass, entry)
    entry.runtime_data = coordinator
    try:
        await coordinator.async_config_entry_first_refresh()
        _remove_obsolete_entities(hass, entry)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        coordinator.start()
    except BaseException:
        await coordinator.async_close()
        raise
    entry.async_on_unload(entry.add_update_listener(_async_reload))

    async def stop(event: Event) -> None:
        await coordinator.async_close()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop))

    if not hass.services.has_service(DOMAIN, "recall_snapshot"):

        async def recall_snapshot(call: ServiceCall) -> None:
            selected = hass.config_entries.async_get_entry(call.data["config_entry_id"])
            if (
                selected is None
                or selected.domain != DOMAIN
                or not hasattr(selected, "runtime_data")
                or selected.state.value != "loaded"
            ):
                raise ServiceValidationError("Select a loaded Behringer X Air integration")
            await selected.runtime_data.async_recall_snapshot(call.data["slot"])

        hass.services.async_register(
            DOMAIN,
            "recall_snapshot",
            recall_snapshot,
            schema=vol.Schema(
                {
                    vol.Required("config_entry_id"): cv.string,
                    vol.Required("slot"): vol.All(vol.Coerce(int), vol.Range(min=1, max=64)),
                }
            ),
        )
    return True


def _remove_obsolete_entities(hass: HomeAssistant, entry: XAirConfigEntry) -> None:
    """Remove only optional entities explicitly removed in this entry's options."""
    prefix = f"{entry.entry_id}_"
    snapshots = {
        f"{prefix}snapshot_{slot:02}"
        for slot in parse_snapshots(entry.options.get(CONF_SNAPSHOTS, DEFAULT_SNAPSHOTS))
    }
    removed_sends = (
        {f"{prefix}ch_{ch:02}_bus_{bus}_volume" for ch in range(1, 17) for bus in range(1, 7)}
        if not entry.options.get(CONF_INCLUDE_SENDS, False)
        else set()
    )
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.platform == DOMAIN and (
            entity.unique_id in removed_sends
            or (
                entity.unique_id.startswith(f"{prefix}snapshot_")
                and entity.unique_id not in snapshots
            )
        ):
            registry.async_remove(entity.entity_id)


async def _async_reload(hass: HomeAssistant, entry: XAirConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: XAirConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.async_close()
    if not any(
        other.entry_id != entry.entry_id and other.state.value == "loaded"
        for other in hass.config_entries.async_entries(DOMAIN)
    ):
        hass.services.async_remove(DOMAIN, "recall_snapshot")
    return True
