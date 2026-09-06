"""Battle-to-world target bridge for POKEROL anime-style environmental orders."""

from copy import deepcopy

from services.pokemon_move_capability_engine import compatible_world_effects
from services.pokemon_world_move_execution_engine import execute_pokemon_world_move, object_world_packet


ENV_BATTLE_BUILD = "0.3.0-effect-aware-targets"


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


def _is_physical_target(obj):
    if not obj:
        return False
    db = getattr(obj, "db", None)
    if db is None:
        return False
    return bool(
        _list(getattr(db, "materials", []))
        or _list(getattr(db, "pokemon_interaction_tags", []))
        or _text(getattr(db, "water_body_id", ""))
        or _dict(getattr(db, "physical_properties", {}))
    )


def environment_targets(actor):
    room = getattr(actor, "location", None) if actor else None
    if not room:
        return []
    rows = []
    for obj in list(getattr(room, "contents", []) or []):
        if obj is actor or not _is_physical_target(obj):
            continue
        packet = object_world_packet(obj)
        rows.append({
            "object_id": _text(getattr(obj.db, "object_id", "")),
            "dbref": int(obj.id),
            "name": _text(getattr(obj, "key", "")),
            "materials": _list(packet.get("materials")),
            "tags": _list(packet.get("tags")),
            "water_body_id": _text(packet.get("water_body_id")),
            "physical_properties": deepcopy(_dict(packet.get("physical_properties"))),
            "environmental_state": deepcopy(_dict(packet.get("environmental_state"))),
        })
    rows.sort(key=lambda row: (row.get("name") or "", row.get("dbref") or 0))
    return rows


def compatible_environment_targets(actor, move):
    output = []
    for row in environment_targets(actor):
        effects = compatible_world_effects(move, {
            "materials": row.get("materials") or [],
            "tags": row.get("tags") or [],
            "physical_properties": row.get("physical_properties") or {},
            "environmental_state": row.get("environmental_state") or {},
        })
        if effects:
            item = deepcopy(row)
            item["effects"] = effects
            output.append(item)
    return output


def resolve_local_target(actor, target_spec):
    room = getattr(actor, "location", None) if actor else None
    if not room:
        return None
    spec = _dict(target_spec)
    wanted_object_id = _text(spec.get("object_id"))
    try:
        wanted_dbref = int(spec.get("dbref")) if spec.get("dbref") is not None else None
    except (TypeError, ValueError):
        wanted_dbref = None
    for obj in list(getattr(room, "contents", []) or []):
        if obj is actor:
            continue
        if wanted_dbref is not None and int(obj.id) == wanted_dbref:
            return obj if _is_physical_target(obj) else None
        if wanted_object_id and _text(getattr(obj.db, "object_id", "")) == wanted_object_id:
            return obj if _is_physical_target(obj) else None
    return None


def _room_environment(actor, target_obj=None):
    room = getattr(actor, "location", None) if actor else None
    water_bodies = _list(getattr(getattr(room, "db", None), "water_bodies", [])) if room else []
    target_packet = object_world_packet(target_obj) if target_obj else {}
    medium_id = _text(target_packet.get("water_body_id"))
    return {
        "line_of_sight": True,
        "ground_contact": True,
        "airspace_available": True,
        "water_available": bool(water_bodies) or "WATER" in {str(v).upper() for v in _list(target_packet.get("materials"))},
        "water_body_id": medium_id or None,
        "shared_water_body": bool(medium_id),
        "weather": _text(_dict(getattr(getattr(room, "db", None), "world_state", {})).get("weather")) or "mild",
    }


def execute_battle_environment_request(actor, pokemon_profile, move, request):
    """Persist one queued battle world request against a verified current-Room target."""
    target_spec = _dict(_dict(request).get("world_target"))
    target_obj = resolve_local_target(actor, target_spec)
    if not target_obj:
        return {"executed": False, "status": "WORLD_TARGET_NOT_LOCAL", "build": ENV_BATTLE_BUILD}
    target_packet = object_world_packet(target_obj)
    result = execute_pokemon_world_move(
        pokemon_profile,
        move,
        target_obj,
        actor=actor,
        environment=_room_environment(actor, target_obj),
        intensity=float(_dict(request).get("intensity") or 1.0),
    )
    return {
        **result,
        "target_object_id": _text(getattr(target_obj.db, "object_id", "")),
        "target_name": _text(getattr(target_obj, "key", "")),
        "target_water_body_id": _text(target_packet.get("water_body_id")) or None,
        "target_materials": _list(target_packet.get("materials")),
        "target_physical_properties": deepcopy(_dict(target_packet.get("physical_properties"))),
        "build": ENV_BATTLE_BUILD,
    }
