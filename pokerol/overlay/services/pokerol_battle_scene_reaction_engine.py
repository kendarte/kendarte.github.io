"""Reactive scene consequences generated from hard battle/world facts.

This bridge does not ask AI whether damage happened. It consumes the persisted
physics result, checks actual Room/NPC authority, and applies deterministic scene
consequences. The DM can narrate the resulting facts afterward.
"""

from copy import deepcopy

from services.pokerol_event_editor_service import OAK_TUTORIAL_EVENT_ID
from services.pokerol_event_progress import mark_event_active
from services.pokerol_player_progress import record_event


BATTLE_SCENE_REACTION_BUILD = "0.1.0-hard-fact-scene-reactions"
LAB_ROOM_ID = "KANTO-PAL-002"
OAK_NPC_ID = "NPC-KANTO-PAL-OAK"
RIVAL_NPC_ID = "NPC-KANTO-PAL-RIVAL"

SEVERE_EVENT_TYPES = {
    "IGNITED", "STRUCTURAL_BREAK", "THERMAL_SHOCK_BREAK", "THERMAL_SHOCK_CRACK",
    "STRUCTURAL_DAMAGE", "MELTED", "FIRE_SPREAD_RISK_INCREASED",
}
SEVERE_MOVE_EFFECTS = {"IGNITE", "BURN", "BREAK", "SHORT_CIRCUIT", "MELT"}
SENSITIVE_TAGS = {"VALUABLE", "ELECTRICAL_DEVICE", "LAB_EQUIPMENT", "FRAGILE_STRUCTURE"}


def _dict(value):
    try:
        return dict(value or {})
    except Exception:
        return {}


def _list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _text(value):
    return str(value or "").strip()


def _room_id(room):
    return _text(getattr(getattr(room, "db", None), "room_id", "")) if room else ""


def _npc(room, npc_id):
    for obj in list(getattr(room, "contents", []) or []) if room else []:
        if _text(getattr(getattr(obj, "db", None), "npc_id", "")) == npc_id:
            return obj
    return None


def _event_types(world_result):
    return {
        _text(_dict(row).get("type")).upper()
        for row in _list(_dict(world_result).get("events"))
        if _text(_dict(row).get("type"))
    }


def _move_effects(move):
    return {str(v).strip().upper() for v in _list(_dict(move).get("world_effects")) if str(v).strip()}


def _target_tags(world_result):
    values = _list(_dict(world_result).get("target_materials"))
    return {str(v).strip().upper() for v in values if str(v).strip()}


def _serious_lab_consequence(move, world_result):
    if not bool(_dict(world_result).get("executed")):
        return False
    events = _event_types(world_result)
    effects = _move_effects(move)
    tags = _target_tags(world_result)
    state = _dict(_dict(world_result).get("persisted_target_state"))
    physical_damage = bool(state.get("burning") or state.get("broken") or state.get("cracked"))
    integrity = state.get("integrity")
    try:
        physical_damage = physical_damage or float(integrity) < 0.75
    except (TypeError, ValueError):
        pass
    return bool(events & SEVERE_EVENT_TYPES or physical_damage or ((effects & SEVERE_MOVE_EFFECTS) and (tags & SENSITIVE_TAGS)))


def _outside_exit(room):
    rows = [ex for ex in list(getattr(room, "exits", []) or []) if getattr(ex, "destination", None) is not None]
    if not rows:
        return None
    def score(ex):
        name = _text(getattr(ex, "key", "")).lower()
        dest = getattr(ex, "destination", None)
        value = 20 if _room_id(dest) and _room_id(dest) != LAB_ROOM_ID else 0
        if any(v in name for v in ("afuera", "salida", "exterior", "outside", "plaza", "pueblo")):
            value += 20
        return value
    rows.sort(key=score, reverse=True)
    return rows[0]


def _emit_oak_intervention(actor, target_name):
    actor.msg("\nProfesor Oak: ¡Se acabó! ¡Los dos afuera antes de que destrocen algo más!")
    actor.msg("\nEl Profesor Oak interrumpe la batalla después de ver el daño en {}.".format(target_name or "el laboratorio"))


def apply_battle_scene_reactions(actor, battle_state, move, world_result, request=None):
    """Apply deterministic reactions to an already-persisted world interaction."""
    state = battle_state if isinstance(battle_state, dict) else {}
    room = getattr(actor, "location", None) if actor else None
    result = _dict(world_result)
    response = {
        "reacted": False,
        "status": "NO_SCENE_REACTION",
        "build": BATTLE_SCENE_REACTION_BUILD,
    }
    if not actor or not room or _room_id(room) != LAB_ROOM_ID:
        return response
    if not _serious_lab_consequence(move, result):
        return response
    if not _npc(room, OAK_NPC_ID):
        return response

    battle_id = _text(state.get("battle_id"))
    marker = _dict(getattr(actor.db, "pokerol_battle_scene_reactions", {}))
    marker_key = "{}:OAK_LAB_DAMAGE".format(battle_id or "ACTIVE")
    if marker.get(marker_key):
        return {**response, "status": "REACTION_ALREADY_APPLIED"}

    target_name = _text(result.get("target_name")) or _text(_dict(request).get("world_target", {}).get("name")) or "el laboratorio"
    marker[marker_key] = {
        "target_name": target_name,
        "target_dbref": result.get("target_dbref"),
        "events": sorted(_event_types(result)),
    }
    actor.db.pokerol_battle_scene_reactions = marker

    # Interrupt the current battle without declaring the tutorial won/lost.
    state["status"] = "COMPLETE"
    state["phase"] = "COMPLETE"
    state["outcome"] = "ABANDONED"
    state["scene_interruption"] = {
        "kind": "NPC_AUTHORITY",
        "npc_id": OAK_NPC_ID,
        "reason": "LAB_DAMAGE",
        "target_name": target_name,
        "target_dbref": result.get("target_dbref"),
    }
    state.setdefault("log", []).append({
        "turn": state.get("turn", 1),
        "phase": "COMPLETE",
        "kind": "SCENE_INTERRUPTION",
        "text": "El Profesor Oak interrumpe la batalla por el daño causado en el laboratorio.",
        "npc_id": OAK_NPC_ID,
        "target_name": target_name,
    })
    _emit_oak_intervention(actor, target_name)

    tutorial = _dict(getattr(actor.db, "pokerol_tutorial", {}))
    if _text(tutorial.get("stage")).upper() == "BATTLE":
        tutorial["stage"] = "RIVAL_CHALLENGE"
        tutorial["battle_id"] = ""
        tutorial["challenge_status"] = "INTERRUPTED_BY_OAK"
        tutorial["lab_intervention"] = True
        tutorial["lab_damage_target"] = target_name
        actor.db.pokerol_tutorial = deepcopy(tutorial)
        mark_event_active(
            actor,
            OAK_TUTORIAL_EVENT_ID,
            stage="RIVAL_CHALLENGE",
            facts={
                "challenge_status": "INTERRUPTED_BY_OAK",
                "lab_damage_target": target_name,
            },
        )

    event_id = OAK_TUTORIAL_EVENT_ID + ":LAB-INTERRUPTION"
    try:
        record_event(
            actor,
            event_id=event_id,
            title="Oak interrumpió la batalla",
            result="INTERRUPTED_BY_OAK",
            room_id=LAB_ROOM_ID,
            data={
                "target_name": target_name,
                "target_dbref": result.get("target_dbref"),
                "battle_id": battle_id,
                "events": sorted(_event_types(result)),
            },
            create_memory=False,
        )
    except Exception:
        pass

    # Move through an authored exit only. If none exists, the interruption still
    # stands and no destination is invented.
    exit_obj = _outside_exit(room)
    destination = getattr(exit_obj, "destination", None) if exit_obj else None
    moved = False
    if destination is not None:
        rival = _npc(room, RIVAL_NPC_ID)
        if rival:
            rival.move_to(destination)
        moved = bool(actor.move_to(destination))

    return {
        "reacted": True,
        "status": "OAK_INTERRUPTED_LAB_BATTLE",
        "npc_id": OAK_NPC_ID,
        "target_name": target_name,
        "battle_id": battle_id,
        "moved_outside": moved,
        "destination_room_id": _room_id(destination) if destination else None,
        "build": BATTLE_SCENE_REACTION_BUILD,
    }
