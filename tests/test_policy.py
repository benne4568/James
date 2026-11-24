

from klausi_guard.policy import Decision, Policy, is_affirmative

P = Policy()


def d(tool, args=None):
    return P.decide(tool, args or {})[0]


def test_read_only_allowed():
    assert d("ha_get_state", {"entity_id": "switch.boiler_emergencyops"}) is Decision.ALLOW
    assert d("ha_search", {"query": "rollo"}) is Decision.ALLOW
    assert d("ha_config_get_automation", {}) is Decision.ALLOW


def test_normal_devices_allowed():
    assert d("ha_call_service", {"domain": "cover", "service": "close_cover", "entity_id": "cover.rollade_schlafzimmer"}) is Decision.ALLOW
    assert d("ha_call_service", {"domain": "climate", "service": "set_temperature", "entity_id": "climate.buro", "data": {"temperature": 21}}) is Decision.ALLOW


def test_sensitive_devices_need_confirmation():
    assert d("ha_call_service", {"domain": "switch", "service": "turn_on", "entity_id": "switch.boiler_elheatstep3"}) is Decision.CONFIRM
    assert d("ha_call_service", {"domain": "switch", "service": "turn_off", "entity_id": "switch.cpap"}) is Decision.CONFIRM
    assert d("ha_call_service", {"domain": "alarm_control_panel", "service": "alarm_disarm"}) is Decision.CONFIRM


def test_unknown_domain_needs_confirmation():
    assert d("ha_call_service", {"domain": "lock", "service": "unlock", "entity_id": "lock.haustuer"}) is Decision.CONFIRM
    assert d("ha_call_service", {"domain": "homeassistant", "service": "restart"}) is Decision.CONFIRM
    assert d("ha_call_service", {"ws_command": "config/entity_registry/remove"}) is Decision.CONFIRM


def test_config_changes_need_confirmation():
    for tool in ["ha_config_set_automation", "ha_restart", "ha_remove_entity", "ha_manage_backup", "ha_set_entity", "something_new"]:
        assert d(tool) is Decision.CONFIRM, tool


def test_todo_allowed():
    assert d("ha_set_todo_item", {"entity_id": "todo.aufgaben", "summary": "Milch"}) is Decision.ALLOW


def test_deny_list():
    p = Policy(deny_tools={"ha_restart"})
    assert p.decide("ha_restart", {})[0] is Decision.DENY


def test_affirmative():
    assert is_affirmative("Ja, mach")
    assert is_affirmative("ok")
    assert is_affirmative("Bestätigt.")
    assert not is_affirmative("Nein")
    assert not is_affirmative("Was meinst du?")
    assert not is_affirmative("japanisch essen")
