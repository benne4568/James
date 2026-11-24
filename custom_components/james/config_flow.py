"""Einrichtungsdialog: Adresse und Zugangsschlüssel des James-Dienstes."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_TOKEN, CONF_URL, DEFAULT_URL, DOMAIN

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default=DEFAULT_URL): str,
        vol.Required(CONF_TOKEN): str,
    }
)


class JamesConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            session = async_get_clientsession(self.hass)
            try:
                async with session.get(f"{url}/health", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        errors["base"] = "cannot_connect"
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            if not errors:
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="James", data={CONF_URL: url, CONF_TOKEN: user_input[CONF_TOKEN]}
                )
        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors=errors)
