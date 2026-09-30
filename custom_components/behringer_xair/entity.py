"""Shared device identity and per-control availability."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import XAirCoordinator


class XAirEntity(CoordinatorEntity[XAirCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: XAirCoordinator, key: str, path: str | None = None) -> None:
        super().__init__(coordinator)
        self.path = path
        # Entry ID remains stable when the IP address is reconfigured.
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        info = coordinator.client.info
        assert info is not None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            manufacturer="Behringer",
            model=info.model,
            name=coordinator.entry.title,
            sw_version=info.firmware,
        )

    @property
    def available(self) -> bool:
        return super().available and (
            self.path is None or self.path in (self.coordinator.data or {})
        )
