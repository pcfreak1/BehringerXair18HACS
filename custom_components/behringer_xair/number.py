"""Volume controls in dB, including optional channel-to-bus sends."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_INCLUDE_SENDS
from .coordinator import XAirConfigEntry, XAirCoordinator
from .entity import XAirEntity
from .model import STRIPS, db_to_fader, fader_to_db, send_path


async def async_setup_entry(
    hass: HomeAssistant, entry: XAirConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    entities = [
        XAirVolume(entry.runtime_data, strip.key, strip.label, strip.fader) for strip in STRIPS
    ]
    if entry.options.get(CONF_INCLUDE_SENDS, False):
        entities.extend(
            XAirVolume(
                entry.runtime_data,
                f"ch_{ch:02}_bus_{bus}",
                f"Channel {ch:02} → Bus {bus}",
                send_path(ch, bus),
            )
            for ch in range(1, 17)
            for bus in range(1, 7)
        )
    async_add_entities(entities)


class XAirVolume(XAirEntity, NumberEntity):
    _attr_translation_key = "volume"
    _attr_native_min_value = -90.0
    _attr_native_max_value = 10.0
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = "dB"
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:tune-vertical"

    def __init__(self, coordinator: XAirCoordinator, key: str, label: str, path: str) -> None:
        super().__init__(coordinator, f"{key}_volume", path)
        self._attr_translation_placeholders = {"channel": label}

    @property
    def native_value(self) -> float | None:
        value = (self.coordinator.data or {}).get(self.path)
        return round(fader_to_db(float(value)), 1) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set(self.path, float(db_to_fader(value)))
