"""Push updates plus periodic state reconciliation for X Air."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import XAirClient, XAirError
from .const import CONF_INCLUDE_SENDS, DEFAULT_PORT, DOMAIN
from .model import STRIPS, send_path
from .osc import OscValue

_LOGGER = logging.getLogger(__name__)


class XAirCoordinator(DataUpdateCoordinator[dict[str, OscValue]]):
    """Keep all entities synchronized from a single mixer connection."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry)
        self.entry = entry
        self.client = XAirClient(entry.data[CONF_HOST], entry.data.get(CONF_PORT, DEFAULT_PORT))
        self.paths = [path for strip in STRIPS for path in (strip.fader, strip.on)]
        if entry.options.get(CONF_INCLUDE_SENDS, False):
            self.paths.extend(send_path(ch, bus) for ch in range(1, 17) for bus in range(1, 7))
        self._cancel_refresh = None
        self._refreshing = False

    async def _async_setup(self) -> None:
        try:
            await self.client.async_connect()
            self.client.start_updates(self.paths)
        except (OSError, XAirError) as err:
            raise UpdateFailed(str(err)) from err

    @callback
    def start(self) -> None:
        """Use a fixed timer: frequent push updates must not postpone reconciliation."""
        self.client.on_update = self._handle_push
        self._cancel_refresh = async_track_time_interval(
            self.hass, self._scheduled_refresh, timedelta(seconds=30)
        )

    async def _scheduled_refresh(self, now: datetime) -> None:
        await self.async_refresh()

    @callback
    def _handle_push(self) -> None:
        if not self._refreshing:
            self.async_set_updated_data(dict(self.client.values))

    async def _async_update_data(self) -> dict[str, OscValue]:
        self._refreshing = True
        try:
            if not self.client.connected:
                await self.client.async_connect()
                self.client.start_updates(self.paths)
                if self._cancel_refresh is not None:
                    self.client.on_update = self._handle_push
            await self.client.async_get_info()
            return await self.client.async_refresh()
        except (OSError, XAirError) as err:
            self.client.values.clear()
            raise UpdateFailed(str(err)) from err
        finally:
            self._refreshing = False

    async def async_set(self, address: str, value: float | int) -> None:
        if not self.last_update_success:
            raise HomeAssistantError("The mixer is unavailable")
        try:
            await self.client.async_set(address, value)
        except (OSError, XAirError) as err:
            raise HomeAssistantError(str(err)) from err

    async def async_recall_snapshot(self, slot: int) -> None:
        if not self.last_update_success:
            raise HomeAssistantError("The mixer is unavailable")
        try:
            await self.client.async_recall_snapshot(slot)
            # Reconcile after recall even if firmware omits individual push updates.
            await self.async_refresh()
            if not self.last_update_success:
                raise HomeAssistantError("Connection lost after snapshot recall")
        except (OSError, XAirError) as err:
            raise HomeAssistantError(str(err)) from err

    async def async_close(self) -> None:
        if self._cancel_refresh:
            self._cancel_refresh()
            self._cancel_refresh = None
        await self.client.async_close()
        await self.async_shutdown()


type XAirConfigEntry = ConfigEntry[XAirCoordinator]
