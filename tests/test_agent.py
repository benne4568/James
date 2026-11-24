"""Testet den Agenten-Ablauf mit einer gefälschten Claude-API und einem gefälschten ha-mcp."""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "james_app"))

from james.agent import Agent  # noqa: E402
from james.config import Config, McpServer  # noqa: E402
from james.mcp_hub import ToolRef  # noqa: E402
from james.memory import Memory  # noqa: E402


def text(t):
    return SimpleNamespace(type="text", text=t)


def tool_use(i, name, inp):
    return SimpleNamespace(type="tool_use", id=i, name=name, input=inp)


def resp(stop, *blocks):
    return SimpleNamespace(stop_reason=stop, content=list(blocks))


class FakeHub:
    def __init__(self):
        self.tools = [{"name": "bat__ha_call_service", "description": "", "input_schema": {"type": "object"}}]
        self.calls = []

    def resolve(self, name):
        return ToolRef(server="bat", name=name.split("__", 1)[1]) if name.startswith("bat__") else None

    async def call(self, ref, args):
        self.calls.append((ref.name, args))
        return "ok", False


class FakeMessages:
    def __init__(self, script):
        self.script = list(script)
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.script.pop(0)


def make_agent(tmp_path, script):
    cfg = Config(anthropic_api_key="x", api_token="t", data_dir=tmp_path,
                 mcp_servers=[McpServer("bat", "http://x", "Bat Cave")])
    hub = FakeHub()
    agent = Agent(cfg, hub, Memory(tmp_path / "memory.json"))
    msgs = FakeMessages(script)
    agent.client = SimpleNamespace(beta=SimpleNamespace(messages=msgs))
    return agent, hub, msgs


def test_safe_action_runs_directly(tmp_path):
    args = {"domain": "cover", "service": "close_cover", "entity_id": "cover.rollo_bad"}
    agent, hub, _ = make_agent(tmp_path, [
        resp("tool_use", tool_use("1", "bat__ha_call_service", args)),
        resp("end_turn", text("Rollo im Bad ist zu.")),
    ])
    answer, _ = asyncio.run(agent.handle("Mach das Rollo im Bad zu"))
    assert answer == "Rollo im Bad ist zu."
    assert hub.calls == [("ha_call_service", args)]


def test_sensitive_action_needs_yes_in_next_turn(tmp_path):
    args = {"domain": "switch", "service": "turn_on", "entity_id": "switch.boiler_elheatstep3"}
    agent, hub, msgs = make_agent(tmp_path, [
        resp("tool_use", tool_use("1", "bat__ha_call_service", args)),
        resp("end_turn", text("Soll ich Heizstab 3 einschalten?")),
    ])
    answer, cid = asyncio.run(agent.handle("Heizstab 3 an"))
    assert hub.calls == []
    conv = agent.conversations[cid]
    result = next(
        m["content"][0]["content"] for m in conv.messages
        if m["role"] == "user" and isinstance(m["content"], list)
    )
    assert "BESTÄTIGUNG NÖTIG" in result
    pid = result.split("ID ")[1].split(",")[0]

    # Bestätigung im selben Zug wird abgelehnt
    out, err = asyncio.run(agent._confirm(conv, pid))
    assert err and hub.calls == []

    # Nach einem "Ja" im nächsten Satz wird ausgeführt
    msgs.script = [
        resp("tool_use", tool_use("2", "confirm_action", {"id": pid})),
        resp("end_turn", text("Heizstab 3 ist an.")),
    ]
    answer, _ = asyncio.run(agent.handle("Ja, mach", cid))
    assert answer == "Heizstab 3 ist an."
    assert hub.calls == [("ha_call_service", args)]


def test_no_is_not_confirmation(tmp_path):
    args = {"domain": "switch", "service": "turn_on", "entity_id": "switch.boiler_elheatstep3"}
    agent, hub, msgs = make_agent(tmp_path, [
        resp("tool_use", tool_use("1", "bat__ha_call_service", args)),
        resp("end_turn", text("Soll ich?")),
    ])
    _, cid = asyncio.run(agent.handle("Heizstab 3 an"))
    pid = next(iter(agent.conversations[cid].pending))
    msgs.script = [
        resp("tool_use", tool_use("2", "confirm_action", {"id": pid})),
        resp("end_turn", text("Ok, lasse ich.")),
    ]
    asyncio.run(agent.handle("Nein, lieber nicht", cid))
    assert hub.calls == []


def test_memory_tools(tmp_path):
    agent, _, msgs = make_agent(tmp_path, [
        resp("tool_use", tool_use("1", "remember", {"note": "Benedikt mag 21 Grad im Büro."})),
        resp("end_turn", text("Gemerkt.")),
    ])
    asyncio.run(agent.handle("Merk dir, ich mag 21 Grad im Büro"))
    assert "21 Grad" in agent.memory.as_prompt()
