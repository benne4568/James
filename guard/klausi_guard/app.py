"""HTTP-Seite des Wächters.

- /mcp     MCP-Server für OpenJarvis (Bearer-Token)
- /turn    die HA-Integration meldet jeden Satz des Nutzers (Bearer-Token)
- /health  ohne Anmeldung
"""

from __future__ import annotations

import hmac
from typing import Any

from mcp import types
from mcp.server.lowlevel import Server
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from . import __version__
from .guard import Guard


class TokenMiddleware:
    def __init__(self, app: ASGIApp, token: str):
        self.app = app
        self.token = token.encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path") != "/health":
            headers = dict(scope.get("headers") or [])
            given = headers.get(b"authorization", b"").removeprefix(b"Bearer ").strip()
            if not hmac.compare_digest(given, self.token):
                await JSONResponse({"error": "unauthorized"}, status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)


def create_app(guard: Guard, token: str, host: str = "0.0.0.0") -> ASGIApp:
    async def on_list_tools(_ctx: Any, _params: Any) -> types.ListToolsResult:
        if not guard.upstreams.tools:
            await guard.upstreams.refresh()
        return types.ListToolsResult(tools=guard.list_tools())

    async def on_call_tool(_ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        text, is_error = await guard.call(params.name, params.arguments)
        return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=is_error)

    server = Server(
        "klausi-waechter",
        version=__version__,
        instructions="Home Assistant über Klausis Sicherheitsregeln. Heikles erst nach Bestätigung.",
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )

    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"ok": True, "tools": len(guard.upstreams.tools), "turn": guard.turn})

    async def turn(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except ValueError:
            return JSONResponse({"error": "JSON erwartet"}, status_code=400)
        guard.user_turn(str(body.get("text") or ""))
        return JSONResponse({"ok": True, "turn": guard.turn, "pending": len(guard.pending)})

    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,  # einfache JSON-Antworten, versteht jeder MCP-Client
        host=host,
        custom_starlette_routes=[
            Route("/health", health, methods=["GET"]),
            Route("/turn", turn, methods=["POST"]),
        ],
    )
    return TokenMiddleware(app, token)
