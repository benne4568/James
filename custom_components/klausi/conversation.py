"""Gesprächs-Agent: reicht jeden Satz an OpenJarvis weiter.

Vorher wird der Satz dem Klausi-Wächter gemeldet. Nur so kann der Wächter
prüfen, ob ein „Ja“ wirklich vom Nutzer kam, bevor er heikle Aktionen ausführt.
"""

from __future__ import annotations

import logging

import aiohttp

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_GUARD_TOKEN,
    CONF_GUARD_URL,
    CONF_JARVIS_KEY,
    CONF_JARVIS_URL,
    CONF_MODEL,
    DOMAIN,
    HISTORY_MESSAGES,
    TIMEOUT_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([KlausiConversationEntity(entry)])


def build_messages(chat_log: conversation.ChatLog) -> list[dict[str, str]]:
    """Bisheriges Gespräch aus Home Assistant im OpenAI-Format."""
    messages = []
    for item in chat_log.content:
        if isinstance(item, conversation.UserContent):
            messages.append({"role": "user", "content": item.content})
        elif isinstance(item, conversation.AssistantContent) and item.content:
            messages.append({"role": "assistant", "content": item.content})
    return messages[-HISTORY_MESSAGES:]


class KlausiConversationEntity(conversation.ConversationEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}, "name": "Klausi"}

    @property
    def supported_languages(self) -> str:
        return MATCH_ALL

    async def _async_handle_message(
        self, user_input: conversation.ConversationInput, chat_log: conversation.ChatLog
    ) -> conversation.ConversationResult:
        data = self._entry.data
        session = async_get_clientsession(self.hass)
        timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)

        try:
            async with session.post(
                f"{data[CONF_GUARD_URL]}/turn",
                json={"text": user_input.text},
                headers={"Authorization": f"Bearer {data[CONF_GUARD_TOKEN]}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
        except (aiohttp.ClientError, TimeoutError) as err:
            # Ohne Wächter laufen heikle Aktionen ohnehin nicht. Antworten geht trotzdem.
            _LOGGER.warning("Klausi-Wächter nicht erreichbar: %s", err)

        messages = build_messages(chat_log)
        if not messages or messages[-1] != {"role": "user", "content": user_input.text}:
            messages.append({"role": "user", "content": user_input.text})
        payload = {"model": data[CONF_MODEL], "messages": messages}
        try:
            async with session.post(
                f"{data[CONF_JARVIS_URL]}/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {data[CONF_JARVIS_KEY]}"},
                timeout=timeout,
            ) as resp:
                resp.raise_for_status()
                body = await resp.json()
            speech = (body["choices"][0]["message"].get("content") or "").strip() or "Dazu habe ich keine Antwort."
        except (aiohttp.ClientError, TimeoutError, KeyError, IndexError, ValueError) as err:
            _LOGGER.error("OpenJarvis nicht erreichbar oder Antwort unlesbar: %s", err)
            speech = "Ich erreiche mein Gehirn gerade nicht."

        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(agent_id=user_input.agent_id, content=speech)
        )
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(speech)
        return conversation.ConversationResult(
            response=response, conversation_id=chat_log.conversation_id
        )
