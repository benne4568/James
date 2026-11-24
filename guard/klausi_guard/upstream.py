"""Verbindung zu den echten MCP-Servern (ha-mcp Bat Cave, Opa).

Jeder Aufruf öffnet eine eigene, kurze Verbindung. Das kostet ein paar
Millisekunden, übersteht aber Neustarts von Home Assistant ohne Hänger.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client

from .config import Upstream

log = logging.getLogger(__name__)
SEP = "__"
MAX_TEXT = 60_000


@dataclass
class ToolRef:
    server: str
    name: str


class Upstreams:
    def __init__(self, servers: list[Upstream]):
        self.servers = {s.name: s for s in servers}
        self.tools: list[types.Tool] = []
        self.refs: dict[str, ToolRef] = {}

    async def refresh(self) -> None:
        tools: list[types.Tool] = []
        refs: dict[str, ToolRef] = {}
        for server in self.servers.values():
            try:
                async with streamable_http_client(server.url) as (read, write, *_):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        listed = await session.list_tools()
            except Exception:  # noqa: BLE001 - ein ausgefallener Server soll die anderen nicht stoppen
                log.exception("MCP-Server %s nicht erreichbar", server.name)
                continue
            for tool in listed.tools:
                full = f"{server.name}{SEP}{tool.name}"[:64]
                tools.append(
                    types.Tool(
                        name=full,
                        description=f"[{server.name}] {tool.description or ''}"[:4000],
                        input_schema=tool.input_schema or {"type": "object", "properties": {}},
                    )
                )
                refs[full] = ToolRef(server=server.name, name=tool.name)
            log.info("MCP-Server %s: %d Werkzeuge", server.name, len(listed.tools))
        self.tools, self.refs = tools, refs

    def resolve(self, full_name: str) -> ToolRef | None:
        return self.refs.get(full_name)

    async def call(self, ref: ToolRef, args: dict) -> tuple[str, bool]:
        server = self.servers[ref.server]
        try:
            async with streamable_http_client(server.url) as (read, write, *_):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(ref.name, args, read_timeout_seconds=120)
        except Exception as exc:  # noqa: BLE001
            log.exception("Werkzeug %s fehlgeschlagen", ref.name)
            return f"Fehler beim Aufruf von {ref.name}: {exc}", True
        parts = []
        for item in getattr(result, "content", None) or []:
            text = getattr(item, "text", None)
            parts.append(text if text is not None else f"[{getattr(item, 'type', 'inhalt')}]")
        text = "\n".join(parts) or "(keine Ausgabe)"
        if len(text) > MAX_TEXT:
            text = text[:MAX_TEXT] + "\n[... gekürzt, frage gezielter nach]"
        return text, bool(getattr(result, "is_error", False))
