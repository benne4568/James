"""Startpunkt: python -m klausi_guard"""

from __future__ import annotations

import asyncio
import logging

import uvicorn

from . import config as config_mod
from .app import create_app
from .guard import Guard
from .policy import Policy
from .upstream import Upstreams


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = config_mod.load()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    upstreams = Upstreams(cfg.upstreams)
    await upstreams.refresh()
    guard = Guard(
        upstreams,
        Policy(cfg.extra_sensitive, cfg.deny_tools),
        audit_path=cfg.data_dir / "audit.log",
        owner=cfg.owner,
        confirm_window=cfg.confirm_window_seconds,
    )
    app = create_app(guard, cfg.token, cfg.host)
    logging.getLogger("klausi").info("Wächter läuft auf Port %d mit %d Werkzeugen", cfg.port, len(upstreams.tools))
    await uvicorn.Server(uvicorn.Config(app, host=cfg.host, port=cfg.port, log_level="info")).serve()


if __name__ == "__main__":
    asyncio.run(main())
