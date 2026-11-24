"""Sicherheitsregeln: welche Werkzeugaufrufe Klausi frei ausführen darf.

Drei Stufen:
- ALLOW:   sofort ausführen (lesen, normale Geräte schalten, Aufgaben)
- CONFIRM: erst nach ausdrücklichem Ja des Nutzers im nächsten Satz
- DENY:    nie ausführen

Die Regeln gelten für die Werkzeuge des ha-mcp-Servers. Unbekannte Werkzeuge
landen immer bei CONFIRM, damit ein neues Werkzeug nie ungefragt etwas ändert.
"""

from __future__ import annotations

import json
import re
from enum import Enum


class Decision(str, Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"


READ_ONLY_PREFIXES = (
    "ha_get_",
    "ha_search",
    "ha_list_",
    "ha_config_get_",
    "ha_config_list_",
    "ha_eval_template",
)

# Werkzeuge, die zwar schreiben, aber nur Alltägliches tun
EVERYDAY_TOOLS = {"ha_set_todo_item"}

# Werkzeuge, die Geräte schalten: hier entscheidet die Domain der Zielgeräte
SERVICE_TOOLS = {"ha_call_service", "ha_bulk_control"}

SAFE_DOMAINS = {
    "light",
    "cover",
    "climate",
    "media_player",
    "vacuum",
    "lawn_mower",
    "fan",
    "switch",
    "input_boolean",
    "todo",
    "scene",
    "notify",
    "tts",
    "remote",
    "button",
    "homeassistant",  # nur turn_on/turn_off/toggle, siehe SAFE_SERVICES
}

SAFE_SERVICES_FOR_HOMEASSISTANT = {"turn_on", "turn_off", "toggle"}

# Geräte, die nie ohne Rückfrage geschaltet werden (Teile der Entity-ID)
DEFAULT_SENSITIVE_PATTERNS = [
    r"boiler",
    r"thermostat_hc",
    r"thermostat_(damping|solar|pvenabledhw|absent)",
    r"mixer_",
    r"elheat",
    r"emergency",
    r"heizstab",
    r"cpap",
    r"alarm_control_panel",
    r"varta",
    r"ae_cv5",
    r"bitaxe",
    r"kc868",
]

ENTITY_RE = re.compile(r"\b([a-z_]+)\.([a-z0-9_]+)\b")


class Policy:
    def __init__(self, extra_sensitive: list[str] | None = None, deny_tools: set[str] | None = None):
        patterns = DEFAULT_SENSITIVE_PATTERNS + list(extra_sensitive or [])
        self.sensitive = re.compile("|".join(f"(?:{p})" for p in patterns))
        self.deny_tools = deny_tools or set()

    def decide(self, tool: str, args: dict) -> tuple[Decision, str]:
        """Gibt Entscheidung und Begründung zurück. `tool` ist der ha-mcp-Name ohne Präfix."""
        if tool in self.deny_tools:
            return Decision.DENY, "Dieses Werkzeug ist für Klausi gesperrt."

        if tool.startswith(READ_ONLY_PREFIXES):
            return Decision.ALLOW, "nur lesen"

        if tool in EVERYDAY_TOOLS:
            return Decision.ALLOW, "Alltagsaktion"

        if tool in SERVICE_TOOLS:
            return self._decide_service(args)

        return Decision.CONFIRM, "ändert Konfiguration oder System"

    def _decide_service(self, args: dict) -> tuple[Decision, str]:
        if args.get("ws_command"):
            return Decision.CONFIRM, "direkter WebSocket-Befehl"

        blob = json.dumps(args, ensure_ascii=False).lower()
        if self.sensitive.search(blob):
            return Decision.CONFIRM, "betrifft ein heikles Gerät (Heizung, Wärmepumpe, Alarm o. ä.)"

        domains: set[str] = set()
        if isinstance(args.get("domain"), str):
            domains.add(args["domain"])
        for key in ("entity_id", "entity_ids", "target", "operations", "data"):
            if key in args:
                part = json.dumps(args[key], ensure_ascii=False).lower()
                domains.update(d for d, _ in ENTITY_RE.findall(part))

        if not domains:
            return Decision.CONFIRM, "Ziel nicht eindeutig erkennbar"

        unsafe = {d for d in domains if d not in SAFE_DOMAINS}
        if unsafe:
            return Decision.CONFIRM, f"Bereich {', '.join(sorted(unsafe))} braucht Bestätigung"

        if "homeassistant" in domains and args.get("service") not in SAFE_SERVICES_FOR_HOMEASSISTANT:
            return Decision.CONFIRM, "Systemdienst von Home Assistant"

        return Decision.ALLOW, "normales Gerät schalten"


AFFIRMATIVE_RE = re.compile(
    r"^\s*(ja|jo|jep|yes|ok|okay|okey|klar|genau|bitte|mach|mach das|mach es|los|"
    r"bestätigt|bestätige|einverstanden|passt|richtig|gerne|tu das|tu es|go)\b",
    re.IGNORECASE,
)


def is_affirmative(text: str) -> bool:
    return bool(AFFIRMATIVE_RE.search(text or ""))
