"""Channel enable switches: on means unmuted, off means muted."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import XAirConfigEntry, XAirCoordinator
from .entity import XAirEntity
from .model import STRIPS, Strip


async def async_setup_entry(
    hass: HomeAssistant, entry: XAirConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(XAirEnabled(entry.runtime_data, strip) for strip in STRIPS)


class XAirEnabled(XAirEntity, SwitchEntity):
    _attr_translation_key = "enabled"
    _attr_icon = "mdi:volume-high"

    def __init__(self, coordinator: XAirCoordinator, strip: Strip) -> None:
        super().__init__(coordinator, f"{strip.key}_enabled", strip.on)
        self._attr_translation_placeholders = {"channel": strip.label}

    @property
    def is_on(self) -> bool | None:
        value = (self.coordinator.data or {}).get(self.path)
        return bool(value) if value is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set(self.path, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set(self.path, 0)
