"""Einrichtungsdialog: Adressen von OpenJarvis und vom Klausi-Wächter."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_GUARD_TOKEN,
    CONF_GUARD_URL,
    CONF_JARVIS_KEY,
    CONF_JARVIS_URL,
    CONF_MODEL,
    DEFAULT_GUARD_URL,
    DEFAULT_JARVIS_URL,
    DEFAULT_MODEL,
    DOMAIN,
)

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_JARVIS_URL, default=DEFAULT_JARVIS_URL): str,
        vol.Required(CONF_JARVIS_KEY): str,
        vol.Required(CONF_GUARD_URL, default=DEFAULT_GUARD_URL): str,
        vol.Required(CONF_GUARD_TOKEN): str,
        vol.Required(CONF_MODEL, default=DEFAULT_MODEL): str,
    }
)


class KlausiConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = dict(user_input)
            data[CONF_JARVIS_URL] = data[CONF_JARVIS_URL].rstrip("/")
            data[CONF_GUARD_URL] = data[CONF_GUARD_URL].rstrip("/")
            session = async_get_clientsession(self.hass)
            for key, error in ((CONF_JARVIS_URL, "jarvis_unreachable"), (CONF_GUARD_URL, "guard_unreachable")):
                try:
                    async with session.get(f"{data[key]}/health", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status != 200:
                            errors["base"] = error
                except (aiohttp.ClientError, TimeoutError):
                    errors["base"] = error
            if not errors:
                await self.async_set_unique_id(data[CONF_JARVIS_URL])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Klausi", data=data)
        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors=errors)
