import ast
import copy
from pathlib import Path

SERVICE_PATH = Path("siza-world-engine/overlay/services/world_combat_handoff_engine.py")
COMMAND_PATH = Path("siza-world-engine/overlay/commands/world_combat_bridge_commands.py")
service = SERVICE_PATH.read_text(encoding="utf-8")
command = COMMAND_PATH.read_text(encoding="utf-8")
ast.parse(service)
ast.parse(command)

tree = ast.parse(service)
constants = {
    "WORLD_COMBAT_HANDOFF_BUILD",
    "ENCOUNTER_TYPE",
    "PENDING_STATUS",
    "RESOLVED_STATUS",
    "RESULT_OUTCOMES",
    "HISTORY_LIMIT",
}
functions = {
    "_clone",
    "_text",
    "_plain_dict",
    "_plain_list",
    "_participant_ids_from_encounter",
    "_participant_ids_from_result",
    "validate_world_combat_result",
    "_combat_result_participant",
    "build_world_combat_action",
    "_consequence_engine_applied",
    "apply_world_combat_consequences",
    "accept_world_combat_result",
}
selected = []
for node in tree.body:
    if isinstance(node, ast.Assign):
        names = {target.id for target in node.targets if isinstance(target, ast.Name)}
        if names & constants:
            selected.append(node)
    elif isinstance(node, ast.FunctionDef) and node.name in functions:
        selected.append(node)

class FakeTime:
    @staticmethod
    def time():
        return 1234567890

ns = {"copy": copy, "time": FakeTime}
exec(compile(ast.Module(body=selected, type_ignores=[]), str(SERVICE_PATH), "exec"), ns)

results = []
def test(name, fn):
    try:
        fn()
        results.append((name, True, ""))
    except Exception as exc:
        results.append((name, False, str(exc)))

encounter = {
    "encounter_id": "COMBAT-QA-1",
    "encounter_type": "COMBAT_CONFRONTATION",
    "site": {"room_id": "ROOM-AUTH", "dbref": 42, "name": "Plaza Autorizada"},
    "initiator": {"entity_id": "PLAYER:DBREF:1", "name": "Player"},
    "opponents": [{"entity_id": "NPC-QA", "name": "Rival QA"}],
    "stakes": {"fixture": "WORLD_COMBAT_QA"},
    "world_context_tags": ["QA", "RAIN"],
    "source_action_id": "WORLD-ACTION-QA",
}
result = {
    "bridge_build": "world-combat-bridge-v0.1",
    "result_id": "COMBAT-QA-1:RESULT:1",
    "encounter_id": "COMBAT-QA-1",
    "status": "RESOLVED",
    "outcome": "PLAYER_WIN",
    "winner_ids": ["PLAYER:DBREF:1"],
    "defeated_ids": ["NPC-QA"],
    "participants": [
        {"entity_id": "PLAYER:DBREF:1", "result_state": "ACTIVE", "life_remaining": 9, "damage": 11},
        {"entity_id": "NPC-QA", "result_state": "DEFEATED", "life_remaining": 0, "damage": 20},
    ],
    "site": {"room_id": "FORGED", "dbref": 999, "name": "Sitio no autoritativo"},
    "tcg_build": "0.7.0",
}

class DB:
    def __init__(self):
        self.npc_id = ""
        self.pending_tcg_encounter = {
            "status": "PENDING",
            "encounter": copy.deepcopy(encounter),
            "result": None,
            "opened_at": 1,
            "resolved_at": None,
        }
        self.tcg_combat_history = []

class Actor:
    def __init__(self):
        self.db = DB()
        self.id = 1
        self.key = "Player"


def assert_action_contract():
    action = ns["build_world_combat_action"](encounter, result)
    assert action["action_id"] == "TCG_COMBAT_RESOLVED:COMBAT-QA-1:RESULT:1"
    assert action["action_type"] == "TCG_COMBAT_RESOLVED"
    assert action["outcome"] == "PLAYER_WIN"
    assert action["site_dbref"] == 42
    assert action["site_room_id"] == "ROOM-AUTH"
    assert action["site_name"] == "Plaza Autorizada"
    assert action["target_npc_id"] == "NPC-QA"
    assert action["recipient_ids"] == ["NPC-QA"]
    assert action["issuer_id"] == "PLAYER:DBREF:1"
    assert action["source_action_id"] == "WORLD-ACTION-QA"
    assert action["stakes"] == {"fixture": "WORLD_COMBAT_QA"}
    assert action["actor_life_remaining"] == 9
    assert action["target_life_remaining"] == 0


def assert_validation_rejects_forged_identity():
    actor = Actor()
    forged = copy.deepcopy(result)
    forged["winner_ids"] = ["NPC-QA"]
    forged["defeated_ids"] = ["PLAYER:DBREF:1"]
    packet = ns["validate_world_combat_result"](actor, forged)
    assert packet["accepted"] is False
    assert packet["status"] == "OUTCOME_IDENTITY_MISMATCH"


def assert_authority_routing():
    actor = Actor()
    calls = []
    def core(action):
        calls.append(("core", action["action_id"]))
        return {"status": "PROCESSED", "results": [{"status": "APPLIED", "rule_id": "QA-NPC"}]}
    def player(_actor, action):
        calls.append(("player", action["action_id"]))
        return {"status": "NO_MATCHING_PLAYER_CONSEQUENCE", "results": []}
    ns["emit_world_action"] = core
    ns["apply_player_actor_consequences"] = player
    packet = ns["apply_world_combat_consequences"](actor, encounter, result)
    assert packet["accepted"] is True
    assert packet["world_consequences_applied"] is True
    assert packet["status"] == "CONSEQUENCES_APPLIED"
    expected = "TCG_COMBAT_RESOLVED:COMBAT-QA-1:RESULT:1"
    assert calls == [("core", expected), ("player", expected)]


def assert_no_rule_is_safe_noop():
    actor = Actor()
    ns["emit_world_action"] = lambda action: {"status": "NO_REGISTRY", "results": []}
    ns["apply_player_actor_consequences"] = lambda _actor, action: {
        "status": "NO_MATCHING_PLAYER_CONSEQUENCE",
        "results": [],
    }
    packet = ns["apply_world_combat_consequences"](actor, encounter, result)
    assert packet["accepted"] is True
    assert packet["world_consequences_applied"] is False
    assert packet["status"] == "CONSEQUENCES_NOOP"


def assert_accept_persists_and_is_idempotent():
    actor = Actor()
    calls = []
    def apply(_actor, enc, res):
        calls.append(res["result_id"])
        return {
            "status": "CONSEQUENCES_APPLIED",
            "accepted": True,
            "world_consequences_applied": True,
            "action": ns["build_world_combat_action"](enc, res),
            "core_consequence": {"status": "PROCESSED", "results": [{"status": "APPLIED"}]},
            "player_consequence": {"status": "NO_MATCHING_PLAYER_CONSEQUENCE", "results": []},
        }
    ns["apply_world_combat_consequences"] = apply
    first = ns["accept_world_combat_result"](actor, copy.deepcopy(result))
    assert first["accepted"] is True
    assert first["status"] == "RESULT_ACCEPTED"
    assert first["world_consequences_applied"] is True
    assert actor.db.pending_tcg_encounter["status"] == "RESOLVED"
    assert actor.db.pending_tcg_encounter["result"]["result_id"] == result["result_id"]
    assert actor.db.last_tcg_combat_result["result_id"] == result["result_id"]
    assert actor.db.last_tcg_combat_consequence["status"] == "CONSEQUENCES_APPLIED"
    assert len(actor.db.tcg_combat_history) == 1
    assert calls == [result["result_id"]]
    second = ns["accept_world_combat_result"](actor, copy.deepcopy(result))
    assert second["accepted"] is False
    assert second["status"] == "NO_PENDING_ENCOUNTER"
    assert calls == [result["result_id"]]
    assert len(actor.db.tcg_combat_history) == 1


def assert_command_reports_real_state():
    assert 'world_consequences_applied": applied' in command
    assert 'consequence_status": accepted.get("consequence_status")' in command
    assert "SIN REGLA APLICABLE" in command
    assert "aún no aplicará consecuencias persistentes" not in command


test("packet uses authoritative encounter and stable result action id", assert_action_contract)
test("validation rejects forged winner/defeated identity", assert_validation_rejects_forged_identity)
test("accepted combat routes through NPC/world and player consequence authorities", assert_authority_routing)
test("no matching consequence rule is an accepted safe noop", assert_no_rule_is_safe_noop)
test("accept persists consequence result and duplicate callback cannot reapply", assert_accept_persists_and_is_idempotent)
test("browser acknowledgement reports actual consequence state", assert_command_reports_real_state)

for name, passed, error in results:
    print(f"{'PASS' if passed else 'FAIL'} {name}{' :: ' + error if error else ''}")
passed = sum(1 for _, ok, _ in results if ok)
print(f"SIZA World Combat consequence regression: {passed}/{len(results)}")
if passed != len(results):
    raise SystemExit(1)
