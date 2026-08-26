import ast
import base64
import json
import os
import urllib.error
import urllib.request

REPO = os.environ.get("GH_REPOSITORY", "")
TOKEN = os.environ.get("GH_TOKEN", "")
if not REPO or not TOKEN:
    raise RuntimeError("GH_REPOSITORY/GH_TOKEN required")

API = f"https://api.github.com/repos/{REPO}"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
}
SERVICE = "siza-world-engine/overlay/services/world_combat_handoff_engine.py"
COMMAND = "siza-world-engine/overlay/commands/world_combat_bridge_commands.py"


def request(url, *, method="GET", data=None):
    headers = dict(HEADERS)
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")
    else:
        body = None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{method} {url} -> {exc.code}: {exc.read().decode('utf-8', 'replace')}") from exc


def get(path):
    row = request(f"{API}/contents/{path}?ref=main")
    text = base64.b64decode(row["content"].replace("\n", "")).decode("utf-8")
    return {"sha": row["sha"], "text": text}


def put(path, text, sha, message):
    return request(
        f"{API}/contents/{path}",
        method="PUT",
        data={
            "message": message,
            "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            "sha": sha,
            "branch": "main",
        },
    )


service_live = get(SERVICE)
command_live = get(COMMAND)
service = service_live["text"]
command = command_live["text"]

old_import = "import uuid\n\n\nWORLD_COMBAT_HANDOFF_BUILD = \"0.1.0-world-tcg-handoff\""
new_import = "import uuid\n\nfrom services.consequence_engine import emit_world_action\nfrom services.player_recipient_consequence_engine import apply_player_actor_consequences\n\n\nWORLD_COMBAT_HANDOFF_BUILD = \"0.2.0-world-tcg-consequences\""
if old_import not in service:
    raise RuntimeError("world combat import/build anchor changed")
service = service.replace(old_import, new_import, 1)

insert_anchor = "\ndef accept_world_combat_result(actor, result):\n"
if insert_anchor not in service:
    raise RuntimeError("accept_world_combat_result anchor missing")
helpers = r'''

def _combat_result_participant(result, entity_id):
    wanted = _text(entity_id)
    for row in _plain_list((result or {}).get("participants")):
        item = _plain_dict(row)
        if _text(item.get("entity_id")) == wanted:
            return item
    return {}


def build_world_combat_action(encounter, result):
    """Translate one validated TCG result into the normal World consequence action contract."""
    encounter = _plain_dict(encounter)
    result = _plain_dict(result)
    encounter_id = _text(encounter.get("encounter_id"))
    result_id = _text(result.get("result_id")) or f"{encounter_id}:RESULT"
    initiator = _plain_dict(encounter.get("initiator"))
    opponents = [_plain_dict(row) for row in _plain_list(encounter.get("opponents")) if isinstance(row, dict)]
    opponent = opponents[0] if opponents else {}
    site = _plain_dict(encounter.get("site"))
    initiator_id = _text(initiator.get("entity_id"))
    opponent_id = _text(opponent.get("entity_id"))
    player_result = _combat_result_participant(result, initiator_id)
    opponent_result = _combat_result_participant(result, opponent_id)
    winner_ids = [_text(value) for value in _plain_list(result.get("winner_ids")) if _text(value)]
    defeated_ids = [_text(value) for value in _plain_list(result.get("defeated_ids")) if _text(value)]

    return {
        "action_id": f"TCG_COMBAT_RESOLVED:{result_id}",
        "action_type": "TCG_COMBAT_RESOLVED",
        "source": "TCG_COMBAT",
        "encounter_id": encounter_id,
        "result_id": result_id,
        "encounter_type": _text(encounter.get("encounter_type")) or ENCOUNTER_TYPE,
        "source_action_id": _text(encounter.get("source_action_id")),
        "outcome": _text(result.get("outcome")),
        "issuer_id": initiator_id,
        "issuer_name": _text(initiator.get("name")),
        "actor_player_id": initiator_id,
        "actor_name": _text(initiator.get("name")),
        "actor_npc_id": "",
        "target_npc_id": opponent_id,
        "target_name": _text(opponent.get("name")),
        "winner_ids": winner_ids,
        "defeated_ids": defeated_ids,
        "winner_id": winner_ids[0] if winner_ids else "",
        "defeated_id": defeated_ids[0] if defeated_ids else "",
        "actor_result_state": _text(player_result.get("result_state")),
        "actor_life_remaining": player_result.get("life_remaining"),
        "actor_damage": player_result.get("damage"),
        "target_result_state": _text(opponent_result.get("result_state")),
        "target_life_remaining": opponent_result.get("life_remaining"),
        "target_damage": opponent_result.get("damage"),
        "site_dbref": site.get("dbref"),
        "site_room_id": _text(site.get("room_id")),
        "site_name": _text(site.get("name")),
        "recipient_ids": [opponent_id] if opponent_id else [],
        "stakes": _clone(_plain_dict(encounter.get("stakes"))),
        "world_context_tags": [
            _text(value)
            for value in _plain_list(encounter.get("world_context_tags"))
            if _text(value)
        ],
        "participants": _clone(_plain_list(result.get("participants"))),
        "tcg_build": _text(result.get("tcg_build")),
        "tcg_bridge_build": _text(result.get("bridge_build")),
    }


def _consequence_engine_applied(packet):
    if _text((packet or {}).get("status")) != "PROCESSED":
        return False
    return any(_text(row.get("status")) == "APPLIED" for row in _plain_list((packet or {}).get("results")))


def apply_world_combat_consequences(actor, encounter, result):
    """Route one accepted combat fact through existing consequence authorities without hardcoded world mutation."""
    action = build_world_combat_action(encounter, result)
    if not _text(action.get("encounter_id")) or not _text(action.get("result_id")):
        return {
            "status": "INVALID_COMBAT_ACTION",
            "accepted": False,
            "world_consequences_applied": False,
            "build": WORLD_COMBAT_HANDOFF_BUILD,
        }

    actor_npc_id = _text(getattr(actor.db, "npc_id", "")) if actor else ""
    if actor_npc_id:
        action["actor_npc_id"] = actor_npc_id

    core = emit_world_action(action)
    player = apply_player_actor_consequences(actor, action)
    applied = _consequence_engine_applied(core) or _text(player.get("status")) == "APPLIED"
    return {
        "status": "CONSEQUENCES_APPLIED" if applied else "CONSEQUENCES_NOOP",
        "accepted": True,
        "world_consequences_applied": applied,
        "action": _clone(action),
        "core_consequence": _clone(core),
        "player_consequence": _clone(player),
        "build": WORLD_COMBAT_HANDOFF_BUILD,
    }
'''
service = service.replace(insert_anchor, helpers + insert_anchor, 1)

start = service.index("def accept_world_combat_result(actor, result):")
end = service.index("\n\ndef clear_pending_world_combat(actor):", start)
new_accept = r'''def accept_world_combat_result(actor, result):
    """Accept a validated TCG result, persist transport history and route its fact through World consequences."""
    validation = validate_world_combat_result(actor, result)
    if not validation.get("accepted"):
        return validation

    encounter = _plain_dict(validation.get("encounter"))
    consequence = apply_world_combat_consequences(actor, encounter, result)

    pending = _plain_dict(getattr(actor.db, "pending_tcg_encounter", {}))
    pending["status"] = RESOLVED_STATUS
    pending["result"] = _clone(result)
    pending["world_consequence"] = _clone(consequence)
    pending["resolved_at"] = int(time.time())
    actor.db.pending_tcg_encounter = pending
    actor.db.last_tcg_combat_result = _clone(result)
    actor.db.last_tcg_combat_consequence = _clone(consequence)

    history = _plain_list(getattr(actor.db, "tcg_combat_history", []))
    history.append(
        {
            "encounter": _clone(encounter),
            "result": _clone(result),
            "world_consequence": _clone(consequence),
            "accepted_at": int(time.time()),
            "build": WORLD_COMBAT_HANDOFF_BUILD,
        }
    )
    actor.db.tcg_combat_history = history[-HISTORY_LIMIT:]
    return {
        "status": "RESULT_ACCEPTED",
        "accepted": True,
        "encounter_id": _text(result.get("encounter_id")),
        "outcome": _text(result.get("outcome")),
        "world_consequences_applied": bool(consequence.get("world_consequences_applied")),
        "consequence_status": consequence.get("status"),
        "world_consequence": _clone(consequence),
        "build": WORLD_COMBAT_HANDOFF_BUILD,
    }
'''
service = service[:start] + new_accept + service[end:]

old_ack = '''        # This acknowledgement is presentation only. Persistent consequences are a later authority step.\n        self.caller.msg(\n            f"Resultado de combate recibido: {accepted.get('outcome')} | "\n            f"encounter={accepted.get('encounter_id')}"\n        )\n        self.caller.msg(\n            siza_combat_result_accepted=(\n                ({\n                    "encounter_id": accepted.get("encounter_id"),\n                    "outcome": accepted.get("outcome"),\n                    "world_consequences_applied": False,\n                    "bridge_build": WORLD_COMBAT_HANDOFF_BUILD,\n                },),\n                {},\n            )\n        )'''
new_ack = '''        applied = bool(accepted.get("world_consequences_applied"))\n        self.caller.msg(\n            f"Resultado de combate recibido: {accepted.get('outcome')} | "\n            f"encounter={accepted.get('encounter_id')} | "\n            f"consecuencias={'APLICADAS' if applied else 'SIN REGLA APLICABLE'}"\n        )\n        self.caller.msg(\n            siza_combat_result_accepted=(\n                ({\n                    "encounter_id": accepted.get("encounter_id"),\n                    "outcome": accepted.get("outcome"),\n                    "world_consequences_applied": applied,\n                    "consequence_status": accepted.get("consequence_status"),\n                    "bridge_build": WORLD_COMBAT_HANDOFF_BUILD,\n                },),\n                {},\n            )\n        )'''
if old_ack not in command:
    raise RuntimeError("combat result acknowledgement anchor changed")
command = command.replace(old_ack, new_ack, 1)
command = command.replace(
    '"el World Engine aún no aplicará consecuencias persistentes."',
    '"el resultado volverá al World Engine para consecuencias persistentes configuradas."',
    1,
)

# Syntax guard before any write.
ast.parse(service)
ast.parse(command)

# Execute only the pure helper surface with mocked consequence authorities.
tree = ast.parse(service)
wanted = {
    "_clone",
    "_text",
    "_plain_dict",
    "_plain_list",
    "_combat_result_participant",
    "build_world_combat_action",
    "_consequence_engine_applied",
    "apply_world_combat_consequences",
}
selected = []
for node in tree.body:
    if isinstance(node, ast.Assign):
        names = {target.id for target in node.targets if isinstance(target, ast.Name)}
        if names & {"WORLD_COMBAT_HANDOFF_BUILD", "ENCOUNTER_TYPE"}:
            selected.append(node)
    elif isinstance(node, ast.FunctionDef) and node.name in wanted:
        selected.append(node)
ns = {"copy": __import__("copy")}
exec(compile(ast.Module(body=selected, type_ignores=[]), SERVICE, "exec"), ns)

encounter = {
    "encounter_id": "COMBAT-TEST-1",
    "encounter_type": "COMBAT_CONFRONTATION",
    "site": {"room_id": "ROOM-A", "dbref": 42, "name": "Plaza"},
    "initiator": {"entity_id": "PLAYER:DBREF:1", "name": "Player"},
    "opponents": [{"entity_id": "NPC-7", "name": "Rival"}],
    "stakes": {"kind": "QA"},
    "world_context_tags": ["RAIN", "QA"],
    "source_action_id": "SOURCE-1",
}
result = {
    "result_id": "COMBAT-TEST-1:RESULT:1",
    "encounter_id": "COMBAT-TEST-1",
    "outcome": "PLAYER_WIN",
    "winner_ids": ["PLAYER:DBREF:1"],
    "defeated_ids": ["NPC-7"],
    "participants": [
        {"entity_id": "PLAYER:DBREF:1", "result_state": "ACTIVE", "life_remaining": 8, "damage": 12},
        {"entity_id": "NPC-7", "result_state": "DEFEATED", "life_remaining": 0, "damage": 20},
    ],
    "site": {"room_id": "UNTRUSTED", "dbref": 999, "name": "Fake"},
    "tcg_build": "0.7.0",
    "bridge_build": "world-combat-bridge-v0.1",
}
action = ns["build_world_combat_action"](encounter, result)
assert action["action_id"] == "TCG_COMBAT_RESOLVED:COMBAT-TEST-1:RESULT:1"
assert action["action_type"] == "TCG_COMBAT_RESOLVED"
assert action["site_dbref"] == 42 and action["site_room_id"] == "ROOM-A"
assert action["target_npc_id"] == "NPC-7" and action["recipient_ids"] == ["NPC-7"]
assert action["actor_life_remaining"] == 8 and action["target_life_remaining"] == 0
assert action["outcome"] == "PLAYER_WIN" and action["source_action_id"] == "SOURCE-1"
assert ns["build_world_combat_action"](encounter, result)["action_id"] == action["action_id"]

class DB:
    npc_id = ""
class Actor:
    db = DB()
    id = 1
    key = "Player"
actor = Actor()

calls = []
def core_applied(packet):
    calls.append(("core", packet["action_id"]))
    return {"status": "PROCESSED", "results": [{"rule_id": "QA", "status": "APPLIED"}]}
def player_noop(_actor, packet):
    calls.append(("player", packet["action_id"]))
    return {"status": "NO_MATCHING_PLAYER_CONSEQUENCE", "results": []}
ns["emit_world_action"] = core_applied
ns["apply_player_actor_consequences"] = player_noop
applied = ns["apply_world_combat_consequences"](actor, encounter, result)
assert applied["world_consequences_applied"] is True
assert calls == [("core", action["action_id"]), ("player", action["action_id"])]

ns["emit_world_action"] = lambda packet: {"status": "NO_REGISTRY", "results": []}
ns["apply_player_actor_consequences"] = lambda _actor, packet: {"status": "NO_MATCHING_PLAYER_CONSEQUENCE", "results": []}
noop = ns["apply_world_combat_consequences"](actor, encounter, result)
assert noop["world_consequences_applied"] is False and noop["status"] == "CONSEQUENCES_NOOP"

assert 'world_consequences_applied": applied' in command
assert "consequence_status" in command
print("PASS World Combat consequence packet + authority routing + syntax")

# Concurrency guard: both files must still be exact before sequential writes.
latest_service = get(SERVICE)
latest_command = get(COMMAND)
if latest_service != service_live or latest_command != command_live:
    raise RuntimeError("World Combat files changed during guarded migration")

service_put = put(SERVICE, service, latest_service["sha"], "Route accepted TCG combat results through World consequences")
print("SERVICE_COMMIT", service_put["commit"]["sha"])
latest_command = get(COMMAND)
command_put = put(COMMAND, command, latest_command["sha"], "Report World Combat consequence application")
print("COMMAND_COMMIT", command_put["commit"]["sha"])
