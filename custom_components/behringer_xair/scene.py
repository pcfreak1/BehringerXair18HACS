"""Stateless Home Assistant scenes recalling the mixer's internal snapshots."""

from __future__ import annotations

from typing import Any

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SNAPSHOTS, DEFAULT_SNAPSHOTS
from .coordinator import XAirConfigEntry, XAirCoordinator
from .entity import XAirEntity
from .model import parse_snapshots


async def async_setup_entry(
    hass: HomeAssistant, entry: XAirConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    snapshots = parse_snapshots(entry.options.get(CONF_SNAPSHOTS, DEFAULT_SNAPSHOTS))
    async_add_entities(
        XAirSnapshot(entry.runtime_data, slot, label) for slot, label in snapshots.items()
    )


class XAirSnapshot(XAirEntity, Scene):
    _attr_icon = "mdi:playlist-play"

    def __init__(self, coordinator: XAirCoordinator, slot: int, label: str) -> None:
        super().__init__(coordinator, f"snapshot_{slot:02}")
        self.slot = slot
        self._attr_name = label
        self._attr_extra_state_attributes = {"snapshot_slot": slot}

    async def async_activate(self, **kwargs: Any) -> None:
        await self.coordinator.async_recall_snapshot(self.slot)
