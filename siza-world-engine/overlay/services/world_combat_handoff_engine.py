import copy
import time
import uuid

from services.consequence_engine import emit_world_action
from services.player_recipient_consequence_engine import apply_player_actor_consequences


WORLD_COMBAT_HANDOFF_BUILD = "0.2.0-world-tcg-consequences"
ENCOUNTER_TYPE = "COMBAT_CONFRONTATION"
PENDING_STATUS = "PENDING"
RESOLVED_STATUS = "RESOLVED"
RESULT_OUTCOMES = {"PLAYER_WIN", "PLAYER_LOSS"}
HISTORY_LIMIT = 50


def _clone(value):
    try:
        return copy.deepcopy(value)
    except Exception:
        return value


def _text(value):
    return str(value or "").strip()


def _plain_dict(value):
    return dict(value or {}) if isinstance(value, dict) else {}


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _entity_id(obj, *, player=False):
    if not obj:
        return ""
    if not player:
        npc_id = _text(getattr(obj.db, "npc_id", ""))
        if npc_id:
            return npc_id
    explicit = _text(getattr(obj.db, "player_id", "") if player else "")
    if explicit:
        return explicit
    prefix = "PLAYER" if player else "NPC"
    return f"{prefix}:DBREF:{int(obj.id)}"


def _tcg_profile(obj):
    profile = _plain_dict(getattr(obj.db, "tcg_profile", {})) if obj else {}
    out = {}
    for field in ("life", "mf", "prow", "eva"):
        value = profile.get(field)
        if value is None:
            continue
        try:
            out[field] = int(value)
        except (TypeError, ValueError):
            continue
    return out


def _participant(obj, *, player=False):
    return {
        "entity_id": _entity_id(obj, player=player),
        "name": _text(getattr(obj, "key", "")),
        "deck_id": _text(getattr(obj.db, "tcg_deck_id", "")) if obj else "",
        "loadout": _clone(_plain_dict(getattr(obj.db, "tcg_loadout", {}))) if obj else {},
        "world_status": _clone(_plain_dict(getattr(obj.db, "state", {}))) if obj else {},
        "tcg_profile": _tcg_profile(obj),
    }


def _site_packet(location):
    if not location:
        return {"room_id": "", "dbref": None, "name": ""}
    room_id = _text(getattr(location.db, "room_id", "")) or f"DBREF:{int(location.id)}"
    return {"room_id": room_id, "dbref": int(location.id), "name": _text(location.key)}


def build_world_combat_encounter(actor, opponent, *, source_action_id="", stakes=None, encounter_id=""):
    """Build a 1v1 combat handoff from authoritative objects without mutating world state."""
    if not actor:
        return {"status": "NO_ACTOR", "accepted": False, "build": WORLD_COMBAT_HANDOFF_BUILD}
    location = getattr(actor, "location", None)
    if not location:
        return {"status": "NO_LOCATION", "accepted": False, "build": WORLD_COMBAT_HANDOFF_BUILD}
    if not opponent:
        return {"status": "NO_OPPONENT", "accepted": False, "build": WORLD_COMBAT_HANDOFF_BUILD}
    if opponent is actor:
        return {"status": "SELF_OPPONENT", "accepted": False, "build": WORLD_COMBAT_HANDOFF_BUILD}
    if getattr(opponent, "location", None) is not location:
        return {"status": "OPPONENT_NOT_LOCAL", "accepted": False, "build": WORLD_COMBAT_HANDOFF_BUILD}

    player = _participant(actor, player=True)
    enemy = _participant(opponent, player=False)
    if not player["entity_id"] or not enemy["entity_id"]:
        return {"status": "MISSING_ENTITY_ID", "accepted": False, "build": WORLD_COMBAT_HANDOFF_BUILD}

    world_tags = [
        _text(value)
        for value in _plain_list(getattr(location.db, "world_context_tags", []))
        if _text(value)
    ]
    modifiers = [
        _clone(value)
        for value in _plain_list(getattr(location.db, "combat_modifiers", []))
        if isinstance(value, dict)
    ]
    identifier = _text(encounter_id) or f"COMBAT-{int(actor.id)}-{int(opponent.id)}-{uuid.uuid4().hex[:12].upper()}"
    encounter = {
        "bridge_build": WORLD_COMBAT_HANDOFF_BUILD,
        "encounter_id": identifier,
        "encounter_type": ENCOUNTER_TYPE,
        "site": _site_packet(location),
        "initiator": player,
        "opponents": [enemy],
        "allies": [],
        "stakes": _clone(_plain_dict(stakes)),
        "world_modifiers": modifiers,
        "world_context_tags": world_tags,
        "source_action_id": _text(source_action_id),
        "created_at": int(time.time()),
    }
    return {"status": "ENCOUNTER_READY", "accepted": True, "encounter": encounter, "build": WORLD_COMBAT_HANDOFF_BUILD}


def set_pending_world_combat(actor, encounter):
    if not actor or not isinstance(encounter, dict) or not _text(encounter.get("encounter_id")):
        return {"status": "INVALID_ENCOUNTER", "accepted": False, "build": WORLD_COMBAT_HANDOFF_BUILD}
    current = _plain_dict(getattr(actor.db, "pending_tcg_encounter", {}))
    if _text(current.get("status")) == PENDING_STATUS:
        return {
            "status": "ENCOUNTER_ALREADY_PENDING",
            "accepted": False,
            "pending_encounter_id": _text((_plain_dict(current.get("encounter"))).get("encounter_id")),
            "build": WORLD_COMBAT_HANDOFF_BUILD,
        }
    packet = {
        "status": PENDING_STATUS,
        "encounter": _clone(encounter),
        "result": None,
        "opened_at": int(time.time()),
        "resolved_at": None,
        "build": WORLD_COMBAT_HANDOFF_BUILD,
    }
    actor.db.pending_tcg_encounter = packet
    return {"status": "ENCOUNTER_PENDING", "accepted": True, "pending": _clone(packet), "build": WORLD_COMBAT_HANDOFF_BUILD}


def emit_world_combat_encounter(actor, encounter):
    """Send a custom Evennia output command. The payload is not mixed into narrative text."""
    pending = set_pending_world_combat(actor, encounter)
    if not pending.get("accepted"):
        return pending
    actor.msg(
        siza_combat_encounter=(
            (_clone(encounter),),
            {"bridge_build": WORLD_COMBAT_HANDOFF_BUILD},
        )
    )
    return {
        "status": "ENCOUNTER_EMITTED",
        "accepted": True,
        "encounter_id": _text(encounter.get("encounter_id")),
        "build": WORLD_COMBAT_HANDOFF_BUILD,
    }


def _participant_ids_from_encounter(encounter):
    ids = {_text((_plain_dict(encounter.get("initiator"))).get("entity_id"))}
    for row in _plain_list(encounter.get("opponents")):
        if isinstance(row, dict):
            ids.add(_text(row.get("entity_id")))
    ids.discard("")
    return ids


def _participant_ids_from_result(result):
    ids = set()
    for row in _plain_list(result.get("participants")):
        if isinstance(row, dict):
            value = _text(row.get("entity_id"))
            if value:
                ids.add(value)
    return ids


def validate_world_combat_result(actor, result):
    """Validate client combat output against the exact pending authoritative encounter."""
    if not actor:
        return {"status": "NO_ACTOR", "accepted": False, "build": WORLD_COMBAT_HANDOFF_BUILD}
    if not isinstance(result, dict):
        return {"status": "INVALID_RESULT", "accepted": False, "build": WORLD_COMBAT_HANDOFF_BUILD}

    pending = _plain_dict(getattr(actor.db, "pending_tcg_encounter", {}))
    if _text(pending.get("status")) != PENDING_STATUS:
        return {"status": "NO_PENDING_ENCOUNTER", "accepted": False, "build": WORLD_COMBAT_HANDOFF_BUILD}
    encounter = _plain_dict(pending.get("encounter"))
    expected_id = _text(encounter.get("encounter_id"))
    received_id = _text(result.get("encounter_id"))
    if not expected_id or received_id != expected_id:
        return {
            "status": "ENCOUNTER_ID_MISMATCH",
            "accepted": False,
            "expected_encounter_id": expected_id,
            "received_encounter_id": received_id,
            "build": WORLD_COMBAT_HANDOFF_BUILD,
        }
    if _text(result.get("status")) != RESOLVED_STATUS:
        return {"status": "RESULT_NOT_RESOLVED", "accepted": False, "build": WORLD_COMBAT_HANDOFF_BUILD}
    outcome = _text(result.get("outcome"))
    if outcome not in RESULT_OUTCOMES:
        return {"status": "INVALID_OUTCOME", "accepted": False, "build": WORLD_COMBAT_HANDOFF_BUILD}

    expected_participants = _participant_ids_from_encounter(encounter)
    actual_participants = _participant_ids_from_result(result)
    if actual_participants != expected_participants:
        return {
            "status": "PARTICIPANT_MISMATCH",
            "accepted": False,
            "expected_participants": sorted(expected_participants),
            "received_participants": sorted(actual_participants),
            "build": WORLD_COMBAT_HANDOFF_BUILD,
        }

    initiator_id = _text((_plain_dict(encounter.get("initiator"))).get("entity_id"))
    opponents = [_plain_dict(row) for row in _plain_list(encounter.get("opponents")) if isinstance(row, dict)]
    opponent_id = _text(opponents[0].get("entity_id")) if opponents else ""
    winner_ids = {_text(value) for value in _plain_list(result.get("winner_ids")) if _text(value)}
    defeated_ids = {_text(value) for value in _plain_list(result.get("defeated_ids")) if _text(value)}
    expected_winner = initiator_id if outcome == "PLAYER_WIN" else opponent_id
    expected_defeated = opponent_id if outcome == "PLAYER_WIN" else initiator_id
    if winner_ids != {expected_winner} or defeated_ids != {expected_defeated}:
        return {
            "status": "OUTCOME_IDENTITY_MISMATCH",
            "accepted": False,
            "expected_winner": expected_winner,
            "expected_defeated": expected_defeated,
            "build": WORLD_COMBAT_HANDOFF_BUILD,
        }

    return {
        "status": "RESULT_VALID",
        "accepted": True,
        "encounter": _clone(encounter),
        "result": _clone(result),
        "build": WORLD_COMBAT_HANDOFF_BUILD,
    }



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

def accept_world_combat_result(actor, result):
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


def clear_pending_world_combat(actor):
    if actor:
        actor.attributes.remove("pending_tcg_encounter")
    return {"status": "PENDING_CLEARED", "build": WORLD_COMBAT_HANDOFF_BUILD}
