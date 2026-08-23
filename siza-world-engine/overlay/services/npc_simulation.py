from collections import deque

from evennia import search_object, search_tag


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"


def _plain_list(value):
    if not value:
        return []
    try:
        return list(value)
    except Exception:
        return []


def _plain_dict(value):
    if not value:
        return {}
    try:
        return dict(value)
    except Exception:
        return {}


def _npc_candidates():
    return [
        obj
        for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY)
        if getattr(obj.db, "is_npc", False)
    ]


def simulated_npcs():
    """Return all Siza NPCs whose simulation flag is enabled."""
    return [npc for npc in _npc_candidates() if bool(npc.db.simulation_enabled)]


def find_npc(query=""):
    candidates = _npc_candidates()
    if not candidates:
        return None

    query = (query or "").strip().lower()
    if not query:
        return candidates[0] if len(candidates) == 1 else None

    scored = []
    for npc in candidates:
        names = [npc.key]
        try:
            names.extend(npc.aliases.all())
        except Exception:
            pass
        score = 0
        for name in names:
            name_l = str(name).lower()
            if query == name_l:
                score = max(score, 1000)
            elif query in name_l or name_l in query:
                score = max(score, 700)
            else:
                overlap = set(query.split()) & set(name_l.split())
                score = max(score, len(overlap) * 100)
        scored.append((score, npc))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[0][1] if scored and scored[0][0] > 0 else None


def find_room(room_key, room_id=None):
    for obj in search_object(room_key):
        if room_id is None or obj.db.room_id == room_id:
            return obj
    return None


def _exit_is_passable(exit_obj):
    if not exit_obj or not exit_obj.destination:
        return False
    if getattr(exit_obj.db, "hidden", False):
        return False
    if getattr(exit_obj.db, "is_locked", False):
        return False
    state = str(exit_obj.db.door_state or "open")
    return state not in {"closed", "locked"}


def find_path(start_room, target_room):
    """Return a list of Exit objects. Every hop is a real passable Exit."""
    if not start_room or not target_room:
        return []
    if start_room == target_room:
        return []

    queue = deque([(start_room, [])])
    visited = {start_room.id}

    while queue:
        room, path = queue.popleft()
        for exit_obj in list(getattr(room, "exits", []) or []):
            if not _exit_is_passable(exit_obj):
                continue
            destination = exit_obj.destination
            if destination.id in visited:
                continue
            next_path = path + [exit_obj]
            if destination == target_room:
                return next_path
            visited.add(destination.id)
            queue.append((destination, next_path))

    return None


def _routine_entry(npc, index=None):
    routine = _plain_list(npc.db.routine)
    if not routine:
        return None, None
    try:
        current = int(npc.db.routine_index or 0) if index is None else int(index)
    except (TypeError, ValueError):
        current = 0
    current %= len(routine)
    raw = routine[current]
    try:
        entry = {str(k): v for k, v in raw.items()}
    except Exception:
        return None, None
    return current, entry


def _target_room(entry):
    if not entry:
        return None
    return find_room(entry.get("room_key", ""), entry.get("room_id"))


def _advance_routine(npc):
    routine = _plain_list(npc.db.routine)
    if not routine:
        return None, None
    try:
        current = int(npc.db.routine_index or 0)
    except (TypeError, ValueError):
        current = 0
    next_index = (current + 1) % len(routine)
    npc.db.routine_index = next_index
    npc.db.routine_hold_remaining = 0
    return _routine_entry(npc, next_index)


def _entry_duration(entry):
    try:
        return max(0, int((entry or {}).get("duration_ticks", 1) or 0))
    except (TypeError, ValueError):
        return 1


def _routine_activity_kind(entry):
    return str((entry or {}).get("activity_kind") or "IDLE").upper()


def _routine_meta(index, entry):
    return {
        "routine_index": index,
        "routine_id": (entry or {}).get("id"),
        "routine_room_id": (entry or {}).get("room_id"),
        "routine_room_key": (entry or {}).get("room_key"),
        "routine_activity_kind": _routine_activity_kind(entry),
    }


def npc_state(npc):
    if not npc:
        return None
    index, entry = _routine_entry(npc)
    try:
        hold = int(npc.db.routine_hold_remaining or 0)
    except (TypeError, ValueError):
        hold = 0
    return {
        "npc": npc.key,
        "npc_id": npc.db.npc_id,
        "location": npc.location.key if npc.location else None,
        "room_id": npc.location.db.room_id if npc.location else None,
        "job": _plain_dict(npc.db.job),
        "current_activity": npc.db.current_activity,
        "destination_id": npc.db.destination_id,
        "routine_index": index,
        "routine_entry": entry,
        "routine_hold_remaining": hold,
        "simulation_enabled": bool(npc.db.simulation_enabled),
    }


def simstep(npc):
    """Advance one NPC by at most one Room through the real Exit graph."""
    if not npc:
        return {"status": "NO_NPC"}
    if not npc.db.simulation_enabled:
        return {"status": "DISABLED", "npc": npc.key}
    if not npc.location:
        return {"status": "NO_LOCATION", "npc": npc.key}

    index, entry = _routine_entry(npc)
    if entry is None:
        return {"status": "NO_ROUTINE", "npc": npc.key}

    target = _target_room(entry)
    if not target:
        return {
            "status": "BAD_TARGET",
            "npc": npc.key,
            "action_kind": "IDLE",
            **_routine_meta(index, entry),
        }

    if npc.location == target:
        npc.db.current_activity = entry.get("activity") or "en su rutina"
        try:
            hold = int(npc.db.routine_hold_remaining or 0)
        except (TypeError, ValueError):
            hold = 0
        if hold > 0:
            hold -= 1
            npc.db.routine_hold_remaining = hold
            return {
                "status": "WAITING",
                "npc": npc.key,
                "location": npc.location.key,
                "target": target.key,
                "activity": npc.db.current_activity,
                "hold_remaining": hold,
                "action_kind": _routine_activity_kind(entry),
                **_routine_meta(index, entry),
            }

        index, entry = _advance_routine(npc)
        target = _target_room(entry)
        if not target:
            return {
                "status": "BAD_TARGET",
                "npc": npc.key,
                "action_kind": "IDLE",
                **_routine_meta(index, entry),
            }

    npc.db.destination_id = entry.get("room_id")
    path = find_path(npc.location, target)
    if path is None:
        npc.db.current_activity = "esperando una ruta disponible"
        return {
            "status": "NO_PATH",
            "npc": npc.key,
            "from": npc.location.key,
            "target": target.key,
            "destination_id": npc.db.destination_id,
            "action_kind": "IDLE",
            **_routine_meta(index, entry),
        }

    if not path:
        npc.db.current_activity = entry.get("activity") or "en su rutina"
        npc.db.routine_hold_remaining = _entry_duration(entry)
        return {
            "status": "AT_TARGET",
            "npc": npc.key,
            "location": npc.location.key,
            "activity": npc.db.current_activity,
            "hold_remaining": npc.db.routine_hold_remaining,
            "action_kind": _routine_activity_kind(entry),
            **_routine_meta(index, entry),
        }

    exit_obj = path[0]
    source = npc.location
    destination = exit_obj.destination

    exit_obj.at_traverse(npc, destination)
    moved = npc.location == destination

    if not moved:
        npc.db.current_activity = "detenida por una condición del camino"
        return {
            "status": "BLOCKED",
            "npc": npc.key,
            "from": source.key,
            "attempted_exit": exit_obj.key,
            "target": target.key,
            "action_kind": "IDLE",
            **_routine_meta(index, entry),
        }

    if npc.location == target:
        npc.db.current_activity = entry.get("activity") or "en su rutina"
        npc.db.routine_hold_remaining = _entry_duration(entry)
        status = "ARRIVED"
    else:
        npc.db.current_activity = f"en camino a {target.key}"
        npc.db.routine_hold_remaining = 0
        status = "MOVED"

    return {
        "status": status,
        "npc": npc.key,
        "from": source.key,
        "to": npc.location.key,
        "used_exit": exit_obj.key,
        "target": target.key,
        "destination_id": npc.db.destination_id,
        "activity": npc.db.current_activity,
        "hold_remaining": int(npc.db.routine_hold_remaining or 0),
        "action_kind": "MOVE",
        **_routine_meta(index, entry),
    }
