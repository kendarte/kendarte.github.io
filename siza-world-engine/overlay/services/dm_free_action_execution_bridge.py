from uuid import uuid4

from services.action_intent_proposal_engine import build_local_capability_catalog
from services.action_proposal_execution_bridge import execute_validated_object_action_proposal
from services.consequence_engine import emit_world_action
from services.dm_free_action_check_engine import (
    resolve_authored_dm_check,
    resolve_judged_dm_auto,
    resolve_judged_dm_check,
)
from services.interaction_proposal_execution_bridge import execute_validated_interaction_proposal
from services.movement_proposal_execution_bridge import execute_validated_movement_proposal
from services.object_action_input_engine import render_object_action_input_result
from services.player_language_contract import get_actor_turn_language
from services.world_combat_handoff_engine import build_world_combat_encounter, emit_world_combat_encounter


DM_EXECUTION_BRIDGE_BUILD = "dm-0.1.1-authoritative-free-action-execution"


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _find_current_object(actor, dbref, *, include_inventory=True):
    if not actor:
        return None
    try:
        wanted = int(dbref)
    except (TypeError, ValueError):
        return None
    location = getattr(actor, "location", None)
    rows = list(getattr(location, "contents", []) or []) if location else []
    if include_inventory:
        rows.extend(list(getattr(actor, "contents", []) or []))
    return next((obj for obj in rows if getattr(obj, "id", None) == wanted), None)


def _find_current_exit(actor, dbref):
    location = getattr(actor, "location", None) if actor else None
    if not location:
        return None
    try:
        wanted = int(dbref)
    except (TypeError, ValueError):
        return None
    return next((obj for obj in list(getattr(location, "exits", []) or []) if getattr(obj, "id", None) == wanted), None)


def _accepted_capability(capability):
    return {
        "status": "ACCEPTED",
        "accepted": True,
        "proposal": {
            "kind": str(capability.get("kind") or ""),
            "capability_id": str(capability.get("capability_id") or ""),
            "confidence": 1.0,
            "reason": "DM_ADJUDICATOR_AUTHORIZED_EXISTING_CAPABILITY",
        },
        "capability": dict(capability),
    }


def _movement_capability(actor, exit_obj):
    if not actor or not exit_obj:
        return None
    stable_id = str(getattr(exit_obj.db, "exit_id", "") or f"DBREF:{int(exit_obj.id)}")
    wanted = f"MOVE:{stable_id}"
    return next(
        (row for row in build_local_capability_catalog(actor) if str(row.get("capability_id") or "") == wanted),
        None,
    )


def _interaction_capability(actor, target_dbref):
    return next(
        (
            row for row in build_local_capability_catalog(actor)
            if str(row.get("kind") or "") == "INTERACTION" and int(row.get("target_dbref") or 0) == int(target_dbref or 0)
        ),
        None,
    )


def _object_action_capability(actor, target_dbref, action_id):
    return next(
        (
            row for row in build_local_capability_catalog(actor)
            if str(row.get("kind") or "") == "OBJECT_ACTION"
            and int(row.get("target_dbref") or 0) == int(target_dbref or 0)
            and str(row.get("object_action_id") or "") == str(action_id or "")
        ),
        None,
    )


def _world_action_packet(actor, action_type, obj, action_id):
    location = getattr(actor, "location", None)
    return {
        "action_id": action_id,
        "action_type": str(action_type or "").upper(),
        "actor_dbref": int(actor.id),
        "actor_name": str(actor.key),
        "actor_npc_id": str(getattr(actor.db, "npc_id", "") or "") or None,
        "site_dbref": int(location.id) if location and getattr(location, "id", None) is not None else None,
        "site_room_id": str(getattr(getattr(location, "db", None), "room_id", "") or "") if location else None,
        "site_name": str(location.key) if location else None,
        "target_dbref": int(obj.id) if obj and getattr(obj, "id", None) is not None else None,
        "target_name": str(obj.key) if obj else None,
        "object_id": str(getattr(getattr(obj, "db", None), "object_id", "") or "") if obj else None,
        "occurrence": 1,
        "source": "DM_FREE_ACTION",
    }


def _execute_take(actor, step):
    obj = _find_current_object(actor, step.get("target_dbref"), include_inventory=False)
    if not obj or getattr(obj, "location", None) is not getattr(actor, "location", None):
        return {"status": "TAKE_TARGET_NOT_LOCAL", "executed": False}
    if bool(getattr(obj.db, "is_npc", False)) or not bool(getattr(obj.db, "portable", False)):
        return {"status": "TAKE_TARGET_NOT_PORTABLE", "executed": False}
    action_id = f"DM-TAKE-{int(actor.id)}-{int(obj.id)}-{uuid4().hex[:12].upper()}"
    moved = bool(obj.move_to(actor, quiet=True))
    if not moved or getattr(obj, "location", None) is not actor:
        return {"status": "TAKE_MOVE_FAILED", "executed": False, "action_id": action_id}
    consequence = emit_world_action(_world_action_packet(actor, "TAKE", obj, action_id))
    language = get_actor_turn_language(actor)
    rendered = f"You take {obj.key}." if language == "en" else f"Tomas {obj.key}."
    return {
        "status": "TAKE_EXECUTED",
        "executed": True,
        "action_id": action_id,
        "target_dbref": int(obj.id),
        "target_name": str(obj.key),
        "consequence": consequence,
        "rendered_text": rendered,
    }


def _execute_drop(actor, step):
    obj = _find_current_object(actor, step.get("target_dbref"), include_inventory=True)
    location = getattr(actor, "location", None)
    if not obj or getattr(obj, "location", None) is not actor or not location:
        return {"status": "DROP_TARGET_NOT_IN_INVENTORY", "executed": False}
    action_id = f"DM-DROP-{int(actor.id)}-{int(obj.id)}-{uuid4().hex[:12].upper()}"
    moved = bool(obj.move_to(location, quiet=True))
    if not moved or getattr(obj, "location", None) is not location:
        return {"status": "DROP_MOVE_FAILED", "executed": False, "action_id": action_id}
    consequence = emit_world_action(_world_action_packet(actor, "DROP", obj, action_id))
    language = get_actor_turn_language(actor)
    rendered = f"You leave {obj.key} here." if language == "en" else f"Dejas {obj.key} aquí."
    return {
        "status": "DROP_EXECUTED",
        "executed": True,
        "action_id": action_id,
        "target_dbref": int(obj.id),
        "target_name": str(obj.key),
        "consequence": consequence,
        "rendered_text": rendered,
    }


def _execute_movement(actor, step):
    exit_obj = _find_current_exit(actor, step.get("target_dbref"))
    capability = _movement_capability(actor, exit_obj)
    if not capability:
        return {"status": "MOVEMENT_CAPABILITY_STALE", "executed": False}
    return execute_validated_movement_proposal(actor, _accepted_capability(capability))


def _execute_interaction(actor, step, raw_player_input):
    capability = _interaction_capability(actor, step.get("target_dbref"))
    if not capability:
        return {"status": "INTERACTION_CAPABILITY_STALE", "executed": False}
    return execute_validated_interaction_proposal(
        actor,
        _accepted_capability(capability),
        raw_player_input=str(raw_player_input or ""),
    )


def _execute_object_action(actor, step):
    affordance = _plain_dict(step.get("affordance"))
    action_id = str(affordance.get("object_action_id") or "")
    capability = _object_action_capability(actor, step.get("target_dbref"), action_id)
    if not capability:
        return {"status": "OBJECT_ACTION_CAPABILITY_STALE", "executed": False}
    bridge = execute_validated_object_action_proposal(actor, _accepted_capability(capability))
    engine = _plain_dict(bridge.get("world_engine_result"))
    current = _plain_dict(bridge.get("current_capability"))
    rendered = ""
    if engine:
        rendered = str(render_object_action_input_result({
            "status": engine.get("status"),
            "object_name": current.get("target_name") or engine.get("object_name"),
            "object_action_name": current.get("label") or engine.get("object_action_name"),
            "action_result": engine,
        }) or "").strip()
    return {**bridge, "rendered_text": rendered}


def _execute_combat(actor, step):
    opponent = _find_current_object(actor, step.get("target_dbref"), include_inventory=False)
    if not opponent or not bool(getattr(opponent.db, "is_npc", False)):
        return {"status": "COMBAT_TARGET_STALE", "executed": False}
    source_action_id = f"DM-COMBAT-{int(actor.id)}-{int(opponent.id)}-{uuid4().hex[:12].upper()}"
    ready = build_world_combat_encounter(
        actor,
        opponent,
        source_action_id=source_action_id,
        stakes={"player_intent": str(step.get("desired_effect") or "")},
    )
    if not ready.get("accepted"):
        return {**ready, "executed": False}
    emitted = emit_world_combat_encounter(actor, ready.get("encounter") or {})
    return {
        **emitted,
        "executed": bool(emitted.get("accepted")),
        "source_action_id": source_action_id,
        "encounter": ready.get("encounter"),
        "rendered_text": "",
    }


def _execute_one(actor, step, raw_player_input):
    executor = str(step.get("executor") or "").upper()
    if executor == "GENERIC_TAKE":
        return _execute_take(actor, step)
    if executor == "GENERIC_DROP":
        return _execute_drop(actor, step)
    if executor == "MOVEMENT":
        return _execute_movement(actor, step)
    if executor == "INTERACTION":
        return _execute_interaction(actor, step, raw_player_input)
    if executor == "OBJECT_ACTION":
        return _execute_object_action(actor, step)
    if executor == "COMBAT":
        return _execute_combat(actor, step)
    if executor == "AUTHORED_CHECK":
        return resolve_authored_dm_check(actor, step, raw_player_input=raw_player_input)
    if executor == "DM_CHECK":
        return resolve_judged_dm_check(actor, step, raw_player_input=raw_player_input)
    if executor == "DM_AUTO":
        return resolve_judged_dm_auto(actor, step, raw_player_input=raw_player_input)
    return {"status": "EXECUTOR_NOT_IMPLEMENTED", "executed": False, "executor": executor}


def execute_adjudicated_dm_free_action(actor, adjudication, raw_player_input=""):
    """Execute only routes selected by deterministic adjudication/judgment; stop after first failed or combat step."""
    packet = _plain_dict(adjudication)
    if packet.get("status") != "ADMISSIBLE" or packet.get("admissible") is not True:
        return {
            "status": "ADJUDICATION_NOT_ADMISSIBLE",
            "executed": False,
            "results": [],
            "build": DM_EXECUTION_BRIDGE_BUILD,
        }
    results = []
    for step in _plain_list(packet.get("steps")):
        result = _execute_one(actor, _plain_dict(step), raw_player_input)
        results.append(result)
        if not bool(result.get("executed")):
            break
        if str(step.get("executor") or "").upper() == "COMBAT":
            break
    all_executed = bool(results) and all(bool(row.get("executed")) for row in results)
    rendered = [str(row.get("rendered_text") or "").strip() for row in results if str(row.get("rendered_text") or "").strip()]
    campaign_observation = None
    if all_executed:
        # The execution bridge is after deterministic world resolution; no model output is accepted here.
        # Successful movement is observed by Exit.at_post_traverse for every traversal path,
        # including direct player commands. Exclude it here so a DM-routed move is not counted twice.
        from services.dm_campaign_registry import observe_active_campaign_evidence
        action_types = [
            str(row.get("status") or "")
            for row in results
            if str(row.get("status") or "") != "MOVEMENT_EXECUTED"
        ]
        evidence = {
            "authority": "WORLD_ENGINE",
            "source": "DM_FREE_ACTION_EXECUTION",
            "action_types": action_types,
            "results": results,
        }
        if action_types:
            campaign_observation = observe_active_campaign_evidence(actor, evidence)
    return {
        "status": "EXECUTED" if all_executed else "PARTIAL_OR_REJECTED",
        "executed": all_executed,
        "results": results,
        "rendered_text": "\n".join(rendered),
        "campaign_observation": campaign_observation,
        "build": DM_EXECUTION_BRIDGE_BUILD,
    }
