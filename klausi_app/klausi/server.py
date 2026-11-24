"""HTTP-Schnittstelle, über die Home Assistant (oder ein iPhone-Kurzbefehl) mit Klausi spricht."""

from __future__ import annotations

import asyncio
import hmac
import logging

from aiohttp import web

from .agent import Agent

log = logging.getLogger(__name__)


def create_app(agent: Agent, api_token: str) -> web.Application:
    lock = asyncio.Lock()  # ein Gespräch nach dem anderen, damit sich Aktionen nicht überholen

    @web.middleware
    async def auth(request: web.Request, handler):
        if request.path == "/health":
            return await handler(request)
        header = request.headers.get("Authorization", "")
        token = header.removeprefix("Bearer ").strip()
        if not hmac.compare_digest(token, api_token):
            return web.json_response({"error": "unauthorized"}, status=401)
        return await handler(request)

    async def health(_: web.Request) -> web.Response:
        return web.json_response({"ok": True, "tools": len(agent.hub.tools)})

    async def conversation(request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            return web.json_response({"error": "JSON erwartet"}, status=400)
        text = (body.get("text") or "").strip()
        if not text:
            return web.json_response({"error": "text fehlt"}, status=400)
        async with lock:
            answer, cid = await agent.handle(text, body.get("conversation_id"))
        return web.json_response({"response": answer, "conversation_id": cid})

    app = web.Application(middlewares=[auth])
    app.router.add_get("/health", health)
    app.router.add_post("/api/conversation", conversation)
    return app
