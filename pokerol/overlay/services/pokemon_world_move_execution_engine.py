"""Persist already-authorized Pokémon world-move consequences in Evennia.

Physics decides *what physically happens*. This bridge persists target state and
records environmental impacts on affected actors/objects. Combat/HP resolution
remains a separate authority and can consume those impact packets.
"""

from services.pokemon_world_move_resolution_engine import resolve_pokemon_world_move


IMPACT_HISTORY_LIMIT = 30


def _dict(value):
    try:
        return {str(k): v for k, v in (value or {}).items()}
    except Exception:
        return {}


def _list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def object_world_packet(obj):
    if not obj:
        return {}
    return {
        "id": str(getattr(obj, "id", "") or ""),
        "name": str(getattr(obj, "key", "") or ""),
        "materials": _list(getattr(obj.db, "materials", [])),
        "tags": _list(getattr(obj.db, "pokemon_interaction_tags", [])),
        "physical_properties": _dict(getattr(obj.db, "physical_properties", {})),
        "environmental_state": _dict(getattr(obj.db, "environmental_state", {})),
        "water_body_id": str(getattr(obj.db, "water_body_id", "") or ""),
    }


def set_contact_medium(obj, medium_id=None):
    """Mark/unmark an actor/object as physically inside one shared medium."""
    if not obj:
        return {"status": "NO_OBJECT", "changed": False}
    value = str(medium_id or "").strip() or None
    before = getattr(obj.db, "contact_medium_id", None)
    obj.db.contact_medium_id = value
    state = _dict(getattr(obj.db, "environmental_state", {}))
    if value:
        state["water_body_id"] = value
        state["in_shared_medium"] = True
    else:
        state.pop("water_body_id", None)
        state["in_shared_medium"] = False
    obj.db.environmental_state = state
    return {"status": "CONTACT_MEDIUM_SET", "changed": before != value, "medium_id": value}


def _shared_medium_members(location, medium_id):
    medium_id = str(medium_id or "").strip()
    if not location or not medium_id:
        return [], {}
    rows = []
    objects = {}
    for obj in list(getattr(location, "contents", []) or []):
        state = _dict(getattr(obj.db, "environmental_state", {}))
        current = str(getattr(obj.db, "contact_medium_id", "") or state.get("water_body_id") or "").strip()
        if current != medium_id:
            continue
        object_id = str(getattr(obj, "id", "") or "")
        if not object_id:
            continue
        rows.append({"id": object_id, "name": str(obj.key), "distance_m": 0})
        objects[object_id] = obj
    return rows, objects


def _record_impact(obj, impact):
    if not obj:
        return
    packet = dict(impact or {})
    obj.db.last_environmental_impact = packet
    history = _list(getattr(obj.db, "environmental_impacts", []))
    history.append(packet)
    obj.db.environmental_impacts = history[-IMPACT_HISTORY_LIMIT:]


def execute_pokemon_world_move(pokemon_profile, move, target_obj, *, actor=None, environment=None, intensity=1.0):
    """Resolve and persist one world move against a concrete Evennia target."""
    if not target_obj:
        return {"status": "NO_TARGET", "executed": False}

    target_packet = object_world_packet(target_obj)
    env = _dict(environment)
    location = getattr(target_obj, "location", None) or getattr(actor, "location", None)
    medium_id = str(target_packet.get("water_body_id") or env.get("water_body_id") or "").strip()
    member_objects = {}
    if medium_id:
        members, member_objects = _shared_medium_members(location, medium_id)
        env.setdefault("water_body_id", medium_id)
        env.setdefault("shared_water_body", True)
        env.setdefault("medium_members", members)

    result = resolve_pokemon_world_move(
        pokemon_profile,
        move,
        target=target_packet,
        environment=env,
        intensity=intensity,
    )
    if not result.get("allowed"):
        return {**result, "executed": False}

    physics = result.get("physics") or {}
    proposed_target = physics.get("target") or {}
    target_obj.db.environmental_state = _dict(proposed_target.get("environmental_state"))
    target_obj.db.last_pokemon_world_move = {
        "move_id": str((move or {}).get("move_id") or ""),
        "events": _list(result.get("events")),
        "actor_id": str(getattr(actor, "id", "") or "") if actor else None,
    }

    persisted_impacts = []
    for impact in _list(result.get("area_impacts")):
        packet = _dict(impact)
        affected = member_objects.get(str(packet.get("target_id") or ""))
        if affected:
            _record_impact(affected, packet)
            persisted_impacts.append({"target_id": packet.get("target_id"), "dbref": int(affected.id), "effect": packet.get("effect"), "intensity": packet.get("intensity")})

    return {
        **result,
        "executed": True,
        "target_dbref": int(target_obj.id),
        "persisted_target_state": _dict(getattr(target_obj.db, "environmental_state", {})),
        "persisted_area_impacts": persisted_impacts,
    }
