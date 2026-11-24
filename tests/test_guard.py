import asyncio

from klausi_guard.guard import CONFIRM_TOOL, Guard
from klausi_guard.policy import Policy
from klausi_guard.upstream import ToolRef


class FakeUpstreams:
    def __init__(self):
        self.tools = []
        self.calls = []
        self.refs = {
            "bat__ha_get_state": ToolRef("bat", "ha_get_state"),
            "bat__ha_call_service": ToolRef("bat", "ha_call_service"),
            "bat__ha_config_set_automation": ToolRef("bat", "ha_config_set_automation"),
        }

    def resolve(self, name):
        return self.refs.get(name)

    async def call(self, ref, args):
        self.calls.append((ref.name, args))
        return "ok", False


def make():
    up = FakeUpstreams()
    return Guard(up, Policy(), audit_path=None), up


def run(coro):
    return asyncio.run(coro)


def code_of(text):
    return text.split("Code ")[1][:4]


def test_read_runs_directly():
    g, up = make()
    text, err = run(g.call("bat__ha_get_state", {"entity_id": "sensor.x"}))
    assert (text, err) == ("ok", False)
    assert up.calls == [("ha_get_state", {"entity_id": "sensor.x"})]


def test_sensitive_is_held_back():
    g, up = make()
    g.user_turn("Schalte den Heizstab ein")
    text, err = run(g.call("bat__ha_call_service", {"domain": "switch", "service": "turn_on", "entity_id": "switch.boiler_elheatstep3"}))
    assert "BESTÄTIGUNG NÖTIG" in text and not err
    assert up.calls == []


def test_model_cannot_confirm_in_same_turn():
    g, up = make()
    g.user_turn("Leg eine Automation an")
    code = code_of(run(g.call("bat__ha_config_set_automation", {"config": {}}))[0])
    text, err = run(g.call(CONFIRM_TOOL, {"code": code}))
    assert err and up.calls == []


def test_yes_in_next_turn_executes():
    g, up = make()
    g.user_turn("Leg eine Automation an")
    code = code_of(run(g.call("bat__ha_config_set_automation", {"config": {}}))[0])
    g.user_turn("Ja, mach")
    text, err = run(g.call(CONFIRM_TOOL, {"code": code}))
    assert not err and up.calls == [("ha_config_set_automation", {"config": {}})]
    # Code ist danach verbraucht
    assert run(g.call(CONFIRM_TOOL, {"code": code}))[1]


def test_other_answer_drops_pending():
    g, up = make()
    g.user_turn("Leg eine Automation an")
    code = code_of(run(g.call("bat__ha_config_set_automation", {"config": {}}))[0])
    g.user_turn("Nein, lieber doch nicht")
    assert g.pending == {}
    assert run(g.call(CONFIRM_TOOL, {"code": code}))[1]
    assert up.calls == []


def test_unknown_tool():
    g, _ = make()
    assert run(g.call("bat__gibtsnicht", {}))[1]


def test_confirm_tool_listed():
    g, _ = make()
    assert CONFIRM_TOOL in [t.name for t in g.list_tools()]
