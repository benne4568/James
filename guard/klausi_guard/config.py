"""Einstellungen aus Umgebungsvariablen (z. B. aus /etc/klausi/guard.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Upstream:
    name: str
    url: str


@dataclass
class Config:
    token: str
    upstreams: list[Upstream]
    host: str = "0.0.0.0"
    port: int = 8100
    data_dir: Path = Path("/var/lib/klausi")
    owner: str = "Benedikt"
    extra_sensitive: list[str] = field(default_factory=list)
    deny_tools: set[str] = field(default_factory=set)
    confirm_window_seconds: int = 300


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_upstreams(value: str) -> list[Upstream]:
    """Format: "bat=http://ha:9583/geheim,opa=https://…"."""
    result = []
    for item in _split(value):
        name, sep, url = item.partition("=")
        if not sep or not name.strip() or not url.strip():
            raise ValueError(f"KLAUSI_UPSTREAMS: '{item}' hat nicht das Format name=url")
        result.append(Upstream(name=name.strip(), url=url.strip()))
    return result


def load(env: dict[str, str] | None = None) -> Config:
    env = dict(os.environ if env is None else env)
    token = env.get("KLAUSI_TOKEN", "")
    if len(token) < 16:
        raise SystemExit("KLAUSI_TOKEN fehlt oder ist kürzer als 16 Zeichen.")
    upstreams = parse_upstreams(env.get("KLAUSI_UPSTREAMS", ""))
    if not upstreams:
        raise SystemExit("KLAUSI_UPSTREAMS fehlt, z. B. bat=http://homeassistant.local:9583/<pfad>")
    return Config(
        token=token,
        upstreams=upstreams,
        host=env.get("KLAUSI_HOST", "0.0.0.0"),
        port=int(env.get("KLAUSI_PORT", "8100")),
        data_dir=Path(env.get("KLAUSI_DATA_DIR", "/var/lib/klausi")),
        owner=env.get("KLAUSI_OWNER", "Benedikt"),
        extra_sensitive=_split(env.get("KLAUSI_EXTRA_SENSITIVE", "")),
        deny_tools=set(_split(env.get("KLAUSI_DENY_TOOLS", ""))),
        confirm_window_seconds=int(env.get("KLAUSI_CONFIRM_SECONDS", "300")),
    )
