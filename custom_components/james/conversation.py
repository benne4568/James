"""Gesprächs-Agent, der jeden Satz an den James-Dienst weiterreicht."""

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

from .const import CONF_TOKEN, CONF_URL, TIMEOUT_SECONDS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([JamesConversationEntity(entry)])


class JamesConversationEntity(conversation.ConversationEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = {"identifiers": {("james", entry.entry_id)}, "name": "James"}
        # Gesprächs-IDs von Home Assistant auf die von James abbilden
        self._conversations: dict[str, str] = {}

    @property
    def supported_languages(self) -> str:
        return MATCH_ALL

    async def _async_handle_message(
        self, user_input: conversation.ConversationInput, chat_log: conversation.ChatLog
    ) -> conversation.ConversationResult:
        url = self._entry.data[CONF_URL]
        token = self._entry.data[CONF_TOKEN]
        session = async_get_clientsession(self.hass)
        payload = {
            "text": user_input.text,
            "conversation_id": self._conversations.get(chat_log.conversation_id),
            "language": user_input.language,
        }
        try:
            async with session.post(
                f"{url}/api/conversation",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
            speech = data.get("response") or "Keine Antwort erhalten."
            if data.get("conversation_id"):
                self._conversations[chat_log.conversation_id] = data["conversation_id"]
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("James nicht erreichbar: %s", err)
            speech = "Ich erreiche James gerade nicht."

        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(agent_id=user_input.agent_id, content=speech)
        )
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(speech)
        return conversation.ConversationResult(
            response=response, conversation_id=chat_log.conversation_id
        )
