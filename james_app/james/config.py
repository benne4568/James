"""Konfiguration für James.

Liest /data/options.json (Home-Assistant-App) und fällt auf Umgebungsvariablen
zurück, damit James auch außerhalb von Home Assistant (z. B. in Docker) läuft.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

OPTIONS_FILE = Path(os.environ.get("JAMES_OPTIONS_FILE", "/data/options.json"))


@dataclass
class McpServer:
    name: str  # Kurzname, wird als Präfix vor die Werkzeugnamen gesetzt
    url: str
    description: str = ""


@dataclass
class Config:
    anthropic_api_key: str
    api_token: str
    model: str = "claude-opus-5-5"
    effort: str = "low"
    mcp_servers: list[McpServer] = field(default_factory=list)
    data_dir: Path = Path("/data")
    port: int = 8099
    owner_name: str = "Benedikt"
    assistant_name: str = "James"
    history_turns: int = 20
    web_search: bool = True
    extra_sensitive_patterns: list[str] = field(default_factory=list)


def _env_servers() -> list[McpServer]:
    raw = os.environ.get("JAMES_MCP_SERVERS", "")
    servers = []
    for item in filter(None, (s.strip() for s in raw.split(","))):
        name, _, url = item.partition("=")
        servers.append(McpServer(name=name.strip(), url=url.strip()))
    return servers


def load() -> Config:
    opts: dict = {}
    if OPTIONS_FILE.exists():
        opts = json.loads(OPTIONS_FILE.read_text(encoding="utf-8"))

    def get(key: str, env: str, default=None):
        value = opts.get(key)
        if value in (None, ""):
            value = os.environ.get(env, default)
        return value

    servers = [
        McpServer(name=s["name"], url=s["url"], description=s.get("description", ""))
        for s in opts.get("mcp_servers", [])
    ] or _env_servers()

    api_key = get("anthropic_api_key", "ANTHROPIC_API_KEY")
    token = get("api_token", "JAMES_API_TOKEN")
    if not api_key:
        raise SystemExit("anthropic_api_key fehlt")
    if not token:
        raise SystemExit("api_token fehlt (schützt die James-Schnittstelle)")

    return Config(
        anthropic_api_key=api_key,
        api_token=token,
        model=get("model", "JAMES_MODEL", "claude-opus-5-5"),
        effort=get("effort", "JAMES_EFFORT", "low"),
        mcp_servers=servers,
        data_dir=Path(get("data_dir", "JAMES_DATA_DIR", "/data")),
        port=int(get("port", "JAMES_PORT", 8099)),
        owner_name=get("owner_name", "JAMES_OWNER", "Benedikt"),
        assistant_name=get("assistant_name", "JAMES_NAME", "James"),
        history_turns=int(get("history_turns", "JAMES_HISTORY_TURNS", 20)),
        web_search=str(get("web_search", "JAMES_WEB_SEARCH", "true")).lower() != "false",
        extra_sensitive_patterns=list(opts.get("extra_sensitive_patterns", [])),
    )
