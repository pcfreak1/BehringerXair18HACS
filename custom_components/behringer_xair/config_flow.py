"""UI setup, reconfiguration and optional mixer controls."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import selector

from .api import UnsupportedMixer, XAirClient, XAirError
from .const import (
    CONF_INCLUDE_SENDS,
    CONF_SNAPSHOTS,
    DEFAULT_PORT,
    DEFAULT_SNAPSHOTS,
    DOMAIN,
)
from .model import parse_snapshots

_LOGGER = logging.getLogger(__name__)


def _connection_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
            vol.Optional(CONF_NAME, default=defaults.get(CONF_NAME, "X Air")): str,
        }
    )


class XAirConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> XAirOptionsFlow:
        return XAirOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._connection_step("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._connection_step("reconfigure", user_input)

    async def _connection_step(
        self, step: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry() if step == "reconfigure" else None
        defaults = dict(entry.data) if entry else {}
        errors = {}
        if user_input is not None:
            data = dict(user_input)
            data[CONF_HOST] = data[CONF_HOST].strip()
            defaults = data
            client = XAirClient(data[CONF_HOST], data[CONF_PORT])
            try:
                info = await client.async_connect()
            except UnsupportedMixer:
                errors["base"] = "unsupported_model"
            except (XAirError, OSError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected mixer connection error")
                errors["base"] = "unknown"
            else:
                unique_id = f"{info.host}:{data[CONF_PORT]}"
                if any(
                    other.unique_id == unique_id
                    and (entry is None or other.entry_id != entry.entry_id)
                    for other in self._async_current_entries()
                ):
                    return self.async_abort(reason="already_configured")
                await self.async_set_unique_id(unique_id)
                data[CONF_NAME] = data.get(CONF_NAME, "").strip() or info.name or "X Air"
                if entry:
                    return self.async_update_reload_and_abort(
                        entry,
                        unique_id=unique_id,
                        title=data[CONF_NAME],
                        data_updates=data,
                    )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=data[CONF_NAME], data=data)
            finally:
                await client.async_close()
        return self.async_show_form(
            step_id=step, data_schema=_connection_schema(defaults), errors=errors
        )


class XAirOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors = {}
        defaults = self.config_entry.options
        if user_input is not None:
            defaults = user_input
            try:
                parse_snapshots(user_input[CONF_SNAPSHOTS])
            except (ValueError, TypeError):
                errors[CONF_SNAPSHOTS] = "invalid_snapshots"
            else:
                return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SNAPSHOTS,
                        default=defaults.get(CONF_SNAPSHOTS, DEFAULT_SNAPSHOTS),
                    ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
                    vol.Required(
                        CONF_INCLUDE_SENDS, default=defaults.get(CONF_INCLUDE_SENDS, False)
                    ): bool,
                }
            ),
        )
