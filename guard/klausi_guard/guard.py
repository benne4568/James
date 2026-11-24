"""Kern des Wächters: Regeln anwenden, Rückfragen verwalten, protokollieren.

Ablauf einer Rückfrage:
1. Klausi will etwas Heikles tun. Der Wächter führt es NICHT aus, merkt es sich
   mit einem Code und antwortet „BESTÄTIGUNG NÖTIG“.
2. Klausi fragt nach. Die Home-Assistant-Integration meldet jeden neuen Satz
   des Nutzers über /turn an den Wächter.
3. Erst wenn ein NEUER Satz eine klare Zustimmung ist („Ja“, „Mach“ …), darf
   Klausi mit `bestaetigen` den Code einlösen. Jeder andere Satz verwirft
   offene Rückfragen.

So kann das Modell sich die Zustimmung nicht selbst geben: Es sieht den Satz
des Nutzers, aber der Wächter prüft ihn unabhängig.
"""

from __future__ import annotations

import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path

from mcp import types

from .policy import Decision, Policy, is_affirmative
from .upstream import ToolRef, Upstreams

log = logging.getLogger(__name__)

CONFIRM_TOOL = "bestaetigen"


@dataclass
class Pending:
    code: str
    ref: ToolRef
    args: dict
    reason: str
    turn: int
    created: float = field(default_factory=time.monotonic)


class Guard:
    def __init__(
        self,
        upstreams: Upstreams,
        policy: Policy,
        audit_path: Path | None = None,
        owner: str = "Benedikt",
        confirm_window: float = 300,
    ):
        self.upstreams = upstreams
        self.policy = policy
        self.audit_path = audit_path
        self.owner = owner
        self.confirm_window = confirm_window
        self.turn = 0
        self.last_text = ""
        self.pending: dict[str, Pending] = {}

    # --- Sätze des Nutzers -------------------------------------------------

    def user_turn(self, text: str) -> None:
        self.turn += 1
        self.last_text = text or ""
        if not is_affirmative(self.last_text) and self.pending:
            self._audit({"event": "pending_dropped", "codes": list(self.pending)})
            self.pending.clear()

    # --- Werkzeuge ---------------------------------------------------------

    def list_tools(self) -> list[types.Tool]:
        confirm = types.Tool(
            name=CONFIRM_TOOL,
            description=(
                f"Führt eine zurückgehaltene Aktion aus. Nur aufrufen, nachdem {self.owner} "
                "im NEUEN Satz klar zugestimmt hat. Der Code steht in der Meldung "
                "„BESTÄTIGUNG NÖTIG“."
            ),
            input_schema={
                "type": "object",
                "properties": {"code": {"type": "string", "description": "Code aus der Rückfrage"}},
                "required": ["code"],
                "additionalProperties": False,
            },
        )
        return [*self.upstreams.tools, confirm]

    async def call(self, name: str, args: dict | None) -> tuple[str, bool]:
        args = dict(args or {})
        if name == CONFIRM_TOOL:
            return await self._confirm(str(args.get("code", "")))

        ref = self.upstreams.resolve(name)
        if ref is None:
            return f"Unbekanntes Werkzeug {name}.", True

        decision, reason = self.policy.decide(ref.name, args)
        if decision is Decision.DENY:
            self._audit({"tool": name, "args": args, "decision": "deny", "reason": reason})
            return f"GESPERRT: {reason}", True

        if decision is Decision.CONFIRM:
            code = f"{secrets.randbelow(10_000):04d}"
            while code in self.pending:
                code = f"{secrets.randbelow(10_000):04d}"
            self.pending[code] = Pending(code=code, ref=ref, args=args, reason=reason, turn=self.turn)
            self._audit({"tool": name, "args": args, "decision": "confirm_requested", "code": code, "reason": reason})
            return (
                f"BESTÄTIGUNG NÖTIG (Code {code}): {reason}. Nichts wurde ausgeführt. "
                f"Sag {self.owner} in einem kurzen Satz, was du tun willst, und frag nach. "
                f"Erst wenn er im nächsten Satz zustimmt, rufe `{CONFIRM_TOOL}` mit Code {code} auf."
            ), False

        text, is_error = await self.upstreams.call(ref, args)
        self._audit({"tool": name, "args": args, "decision": "allow", "error": is_error})
        return text, is_error

    async def _confirm(self, code: str) -> tuple[str, bool]:
        pending = self.pending.get(code)
        if pending is None:
            return "Keine offene Rückfrage mit diesem Code. Frag neu nach.", True
        if time.monotonic() - pending.created > self.confirm_window:
            self.pending.pop(code, None)
            return "Die Rückfrage ist abgelaufen. Frag neu nach.", True
        if self.turn <= pending.turn:
            return (
                f"Noch keine Antwort von {self.owner}. Stell die Frage und warte auf seinen nächsten Satz.",
                True,
            )
        if not is_affirmative(self.last_text):
            self.pending.pop(code, None)
            return f"{self.owner} hat nicht zugestimmt. Aktion verworfen.", True

        self.pending.pop(code, None)
        text, is_error = await self.upstreams.call(pending.ref, pending.args)
        self._audit(
            {"tool": f"{pending.ref.server}__{pending.ref.name}", "args": pending.args,
             "decision": "confirmed", "code": code, "error": is_error}
        )
        return text, is_error

    def _audit(self, entry: dict) -> None:
        entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **entry}
        log.info("audit %s", entry)
        if self.audit_path is None:
            return
        try:
            with self.audit_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            log.exception("Audit-Log nicht schreibbar")
