from services.knowledge_fact_retrieval_engine import retrieve_known_facts
from services.world_event_engine import event_sites


DM_WORLD_CONTEXT_BUILD = "dm-0.1-read-only-world-context"


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


def _aliases(obj):
    try:
        return [str(value) for value in obj.aliases.all() if str(value or "").strip()]
    except Exception:
        return []


def _location_packet(actor):
    site = getattr(actor, "location", None) if actor else None
    if not site:
        return None
    return {
        "name": str(site.key),
        "room_id": str(getattr(site.db, "room_id", "") or "") or None,
        "dbref": int(site.id) if getattr(site, "id", None) is not None else None,
    }


def _entity_packet(obj):
    return {
        "name": str(obj.key),
        "dbref": int(obj.id) if getattr(obj, "id", None) is not None else None,
        "aliases": _aliases(obj),
        "is_npc": bool(getattr(obj.db, "is_npc", False)),
        "npc_id": str(getattr(obj.db, "npc_id", "") or "") or None,
        "object_id": str(getattr(obj.db, "object_id", "") or "") or None,
        "portable": bool(getattr(obj.db, "portable", False)),
    }


def _local_entities(actor):
    site = getattr(actor, "location", None) if actor else None
    if not site:
        return []
    rows = []
    for obj in list(getattr(site, "contents", []) or []):
        if obj is actor or getattr(obj, "destination", None) or bool(getattr(obj.db, "hidden", False)):
            continue
        rows.append(_entity_packet(obj))
    rows.sort(key=lambda row: (0 if row.get("is_npc") else 1, str(row.get("name") or "")))
    return rows


def _inventory(actor):
    if not actor:
        return []
    rows = []
    for obj in list(getattr(actor, "contents", []) or []):
        if getattr(obj, "destination", None) or bool(getattr(obj.db, "hidden", False)):
            continue
        rows.append(_entity_packet(obj))
    rows.sort(key=lambda row: str(row.get("name") or ""))
    return rows


def _local_exits(actor):
    site = getattr(actor, "location", None) if actor else None
    if not site:
        return []
    rows = []
    for exit_obj in list(getattr(site, "exits", []) or []):
        destination = getattr(exit_obj, "destination", None)
        rows.append({
            "name": str(exit_obj.key),
            "aliases": _aliases(exit_obj),
            "exit_dbref": int(exit_obj.id) if getattr(exit_obj, "id", None) is not None else None,
            "exit_id": str(getattr(exit_obj.db, "exit_id", "") or "") or None,
            "destination_name": str(destination.key) if destination else None,
            "destination_room_id": str(getattr(getattr(destination, "db", None), "room_id", "") or "") if destination else None,
            "destination_dbref": int(destination.id) if destination and getattr(destination, "id", None) is not None else None,
        })
    rows.sort(key=lambda row: str(row.get("name") or ""))
    return rows


def _local_active_events(actor):
    location = _location_packet(actor)
    if not location:
        return []
    room_id = str(location.get("room_id") or "")
    dbref = location.get("dbref")
    rows = []
    for site in event_sites():
        same_site = (dbref is not None and getattr(site, "id", None) == dbref) or (
            room_id and str(getattr(site.db, "room_id", "") or "") == room_id
        )
        if not same_site:
            continue
        for raw in _plain_list(getattr(site.db, "world_event_instances", [])):
            event = _plain_dict(raw)
            if not bool(event.get("active", False)):
                continue
            rows.append({
                "id": str(event.get("id") or ""),
                "type": str(event.get("goal_type") or event.get("type") or "EVENT"),
                "priority": event.get("priority"),
                "activity": event.get("activity"),
                "status": event.get("status"),
                "occurrence": event.get("occurrence"),
            })
    rows.sort(key=lambda row: (-int(row.get("priority") or 0), str(row.get("id") or "")))
    return rows


def build_dm_world_snapshot(actor, raw_player_input="", max_known_facts=6, fact_char_budget=1200):
    """Read only the actor's immediate authoritative context needed by the DM for one turn."""
    facts = retrieve_known_facts(
        actor,
        query=str(raw_player_input or ""),
        max_facts=max_known_facts,
        char_budget=fact_char_budget,
    ) if actor else {"selected": [], "selected_fact_ids": [], "context_text": ""}

    return {
        "location": _location_packet(actor),
        "local_entities": _local_entities(actor),
        "inventory": _inventory(actor),
        "local_exits": _local_exits(actor),
        "active_local_events": _local_active_events(actor),
        "player": {
            "name": getattr(actor, "key", None) if actor else None,
            "npc_id": str(getattr(getattr(actor, "db", None), "npc_id", "") or "") if actor else None,
            "known_fact_ids": list(facts.get("selected_fact_ids") or []),
            "known_facts": list(facts.get("selected") or []),
            "known_fact_context": str(facts.get("context_text") or ""),
        },
        "query": str(raw_player_input or ""),
        "build": DM_WORLD_CONTEXT_BUILD,
    }
