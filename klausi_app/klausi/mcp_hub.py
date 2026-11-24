"""Verbindung zu den MCP-Servern (z. B. ha-mcp für Home Assistant).

Jeder Server bekommt einen Kurznamen; seine Werkzeuge erscheinen für Claude als
`<kurzname>__<werkzeug>`, damit gleichnamige Werkzeuge zweier Instanzen
(Bat Cave und Opa) nicht kollidieren.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
from dataclasses import dataclass

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from .config import McpServer

log = logging.getLogger(__name__)
SEP = "__"


@dataclass
class ToolRef:
    server: str
    name: str


class McpHub:
    def __init__(self, servers: list[McpServer]):
        self.servers = servers
        self._sessions: dict[str, ClientSession] = {}
        self._stack = AsyncExitStack()
        self.tools: list[dict] = []  # Claude-Werkzeugdefinitionen
        self._refs: dict[str, ToolRef] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        for server in self.servers:
            try:
                read, write = await self._stack.enter_async_context(streamable_http_client(server.url))
                session = await self._stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                self._sessions[server.name] = session
                listed = await session.list_tools()
                for tool in listed.tools:
                    full = f"{server.name}{SEP}{tool.name}"[:64]
                    desc = tool.description or ""
                    if server.description:
                        desc = f"[{server.description}] {desc}"
                    self.tools.append(
                        {
                            "name": full,
                            "description": desc[:4000],
                            "input_schema": getattr(tool, "input_schema", None) or {"type": "object", "properties": {}},
                        }
                    )
                    self._refs[full] = ToolRef(server=server.name, name=tool.name)
                log.info("MCP-Server %s verbunden, %d Werkzeuge", server.name, len(listed.tools))
            except Exception:  # noqa: BLE001 - ein ausgefallener Server soll Klausi nicht stoppen
                log.exception("MCP-Server %s nicht erreichbar", server.name)

    async def close(self) -> None:
        await self._stack.aclose()

    def resolve(self, full_name: str) -> ToolRef | None:
        return self._refs.get(full_name)

    async def call(self, ref: ToolRef, args: dict) -> tuple[str, bool]:
        """Ruft ein Werkzeug auf. Gibt (Text, ist_fehler) zurück."""
        session = self._sessions.get(ref.server)
        if session is None:
            return f"Server {ref.server} ist nicht verbunden.", True
        try:
            result = await session.call_tool(ref.name, args, read_timeout_seconds=120)
        except Exception as exc:  # noqa: BLE001
            log.exception("Werkzeug %s fehlgeschlagen", ref.name)
            return f"Fehler beim Aufruf von {ref.name}: {exc}", True

        parts = []
        for item in getattr(result, "content", []) or []:
            text = getattr(item, "text", None)
            parts.append(text if text is not None else f"[{getattr(item, 'type', 'inhalt')}]")
        text = "\n".join(parts) or "(keine Ausgabe)"
        if len(text) > 60_000:
            text = text[:60_000] + "\n[... gekürzt, frage gezielter nach]"
        return text, bool(getattr(result, "is_error", False))
