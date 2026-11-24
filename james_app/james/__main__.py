"""Startpunkt: python -m james"""

from __future__ import annotations

import asyncio
import logging

from aiohttp import web

from . import config as config_mod
from .agent import Agent
from .mcp_hub import McpHub
from .memory import Memory
from .server import create_app


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = config_mod.load()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)

    hub = McpHub(cfg.mcp_servers)
    await hub.start()
    agent = Agent(cfg, hub, Memory(cfg.data_dir / "memory.json"))

    runner = web.AppRunner(create_app(agent, cfg.api_token))
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", cfg.port).start()
    logging.getLogger("james").info(
        "%s läuft auf Port %d mit %d Werkzeugen (Modell %s)",
        cfg.assistant_name, cfg.port, len(hub.tools), cfg.model,
    )
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        await hub.close()


if __name__ == "__main__":
    asyncio.run(main())
