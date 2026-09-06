from datetime import datetime, timezone

from evennia import search_tag

from services.faction_engine import has_active_membership


INFORMATION_BUILD = "0.37.0-information-shared-actions"
EVENT_SITE_TAG = "siza_event_site"
EVENT_SITE_CATEGORY = "siza_world_event"
EVENT_AWARENESS_AUDIENCE = "AUDIENCE"


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _record(value):
    try:
        return {str(key): item for key, item in value.items()}
    except Exception:
        return None


def _npc_id(npc):
    return str(getattr(npc.db, "npc_id", "") or "").strip() if npc else ""


def _npc_job_id(npc):
    try:
        job = dict(getattr(npc.db, "job", {}) or {})
    except Exception:
        job = {}
    return str(job.get("id") or "").strip()


def _audience_matches(npc, incident):
    if not npc or not incident:
        return False
    npc_id = _npc_id(npc)
    if not npc_id:
        return False

    npc_ids = {str(value) for value in _plain_list(incident.get("npc_ids")) if value}
    if npc_ids and npc_id not in npc_ids:
        return False

    job_ids = {str(value) for value in _plain_list(incident.get("job_ids")) if value}
    if job_ids and _npc_job_id(npc) not in job_ids:
        return False

    faction_ids = {str(value) for value in _plain_list(incident.get("faction_ids")) if value}
    if faction_ids and not any(has_active_membership(npc, faction_id) for faction_id in faction_ids):
        return False

    return True


def _event_key(event_id, occurrence):
    return f"{str(event_id or '').strip()}:{int(occurrence or 0)}"


def event_information_records(npc):
    """Persistent information heard from another character, keyed by event occurrence."""
    if not npc:
        return {}
    output = {}
    for key, raw in _plain_dict(getattr(npc.db, "event_information", {})).items():
        item = _record(raw)
        if item is not None:
            output[str(key)] = item
    return output


def _reported_record(npc, incident):
    if not npc or not incident:
        return None
    event_id = str(incident.get("id") or incident.get("event_id") or "").strip()
    occurrence = int(incident.get("occurrence", 0) or 0)
    if not event_id or occurrence <= 0:
        return None
    return event_information_records(npc).get(_event_key(event_id, occurrence))


def event_knowledge_route(npc, incident):
    """Return how this NPC knows one EVENT occurrence without conflating witness and report."""
    if not npc or not incident:
        return {"known": False, "via": "NONE", "record": None}

    goal_type = str(incident.get("goal_type") or incident.get("type") or "EVENT").upper()
    if goal_type != "EVENT":
        return {"known": True, "via": goal_type, "record": None}

    npc_id = _npc_id(npc)
    mode = str(incident.get("awareness_mode") or EVENT_AWARENESS_AUDIENCE).upper()
    if mode == EVENT_AWARENESS_AUDIENCE and _audience_matches(npc, incident):
        return {"known": True, "via": "AUDIENCE", "record": None}

    aware = {str(value) for value in _plain_list(incident.get("aware_npc_ids")) if value}
    if npc_id and npc_id in aware:
        return {"known": True, "via": "WITNESSED", "record": None}

    record = _reported_record(npc, incident)
    if record:
        return {"known": True, "via": "REPORTED", "record": record}

    return {"known": False, "via": "NONE", "record": None}


def knows_event_occurrence(npc, incident):
    return bool(event_knowledge_route(npc, incident).get("known"))


def _event_instances(site):
    output = []
    for raw in _plain_list(getattr(site.db, "world_event_instances", [])):
        item = _record(raw)
        if item is not None:
            output.append(item)
    return output


def _event_history(site):
    output = []
    for raw in _plain_list(getattr(site.db, "world_event_history", [])):
        item = _record(raw)
        if item is not None:
            output.append(item)
    return output


def find_event_occurrence(event_id, occurrence=None):
    """Resolve either the live EVENT occurrence or an archived historical occurrence."""
    wanted = str(event_id or "").strip()
    if not wanted:
        return None, None

    matches = []
    wanted_occurrence = int(occurrence) if occurrence is not None else None
    for site in search_tag(EVENT_SITE_TAG, category=EVENT_SITE_CATEGORY):
        for event in _event_instances(site):
            if str(event.get("id") or "") != wanted:
                continue
            if str(event.get("goal_type") or event.get("type") or "EVENT").upper() != "EVENT":
                continue
            current_occurrence = int(event.get("occurrence", 0) or 0)
            if wanted_occurrence is not None and current_occurrence != wanted_occurrence:
                continue
            rank = 3 if bool(event.get("active", False)) else 2
            matches.append((rank, current_occurrence, site, event))

        for event in _event_history(site):
            if str(event.get("id") or "") != wanted:
                continue
            if str(event.get("goal_type") or event.get("type") or "EVENT").upper() != "EVENT":
                continue
            historical_occurrence = int(event.get("occurrence", 0) or 0)
            if wanted_occurrence is not None and historical_occurrence != wanted_occurrence:
                continue
            matches.append((1, historical_occurrence, site, event))

    if not matches:
        return None, None
    matches.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return matches[0][2], matches[0][3]


def _source_hops(source, event):
    route = event_knowledge_route(source, event)
    if route.get("via") in {"WITNESSED", "AUDIENCE"}:
        return 0, _npc_id(source)
    record = route.get("record") or {}
    try:
        hops = max(1, int(record.get("hops", 1) or 1))
    except (TypeError, ValueError):
        hops = 1
    origin = str(record.get("origin_npc_id") or record.get("source_npc_id") or _npc_id(source))
    return hops, origin


def _emit_information_shared_action(source, target, event_id, occurrence, source_via, candidate_hops, stored_hops, heard_count, created, record):
    """Emit a structured consequence action only after information was actually persisted."""
    try:
        from services.consequence_engine import emit_world_action
    except Exception as exc:
        return {"status": "IMPORT_ERROR", "error": str(exc)}

    source_id = _npc_id(source)
    target_id = _npc_id(target)
    action_id = (
        f"INFORMATION_SHARED:{event_id}:{int(occurrence)}:{source_id}:{target_id}:{int(heard_count or 0)}"
    )
    return emit_world_action(
        {
            "action_id": action_id,
            "action_type": "INFORMATION_SHARED",
            "actor_npc_id": source_id,
            "actor_name": source.key,
            "target_npc_id": target_id,
            "target_name": target.key,
            "event_id": event_id,
            "occurrence": int(occurrence),
            "source_via": source_via,
            "candidate_hops": int(candidate_hops or 0),
            "hops": int(stored_hops or 0),
            "heard_count": int(heard_count or 0),
            "created": bool(created),
            "origin_npc_id": str((record or {}).get("origin_npc_id") or source_id),
            "recipient_ids": [target_id],
        }
    )


def share_event_information(source, target, event_id, occurrence=None):
    """Direct local communication of one known EVENT occurrence; never mutates witness snapshot."""
    source_id = _npc_id(source)
    target_id = _npc_id(target)
    if not source_id or not target_id:
        return {"success": False, "reason": "BAD_NPC"}
    if source_id == target_id:
        return {"success": False, "reason": "SAME_NPC"}
    if not getattr(source, "location", None) or source.location != getattr(target, "location", None):
        return {"success": False, "reason": "NOT_COLOCATED"}

    site, event = find_event_occurrence(event_id, occurrence=occurrence)
    if not event:
        return {"success": False, "reason": "EVENT_NOT_FOUND"}

    source_route = event_knowledge_route(source, event)
    if not source_route.get("known"):
        return {
            "success": False,
            "reason": "SOURCE_NOT_AWARE",
            "event_id": event.get("id"),
            "occurrence": event.get("occurrence"),
        }

    target_route = event_knowledge_route(target, event)
    if target_route.get("via") in {"WITNESSED", "AUDIENCE"}:
        return {
            "success": True,
            "created": False,
            "reason": "TARGET_ALREADY_DIRECTLY_AWARE",
            "event_id": event.get("id"),
            "occurrence": event.get("occurrence"),
            "target_via": target_route.get("via"),
        }

    now = datetime.now(timezone.utc).isoformat()
    event_id = str(event.get("id") or "")
    occurrence = int(event.get("occurrence", 0) or 0)
    key = _event_key(event_id, occurrence)
    records = event_information_records(target)
    existing = dict(records.get(key) or {})
    created = not bool(existing)
    source_hops, origin_npc_id = _source_hops(source, event)
    candidate_hops = source_hops + 1

    try:
        existing_hops = int(existing.get("hops")) if existing.get("hops") is not None else None
    except (TypeError, ValueError):
        existing_hops = None
    better_route = created or existing_hops is None or candidate_hops < existing_hops

    sources = [str(value) for value in _plain_list(existing.get("source_npc_ids")) if value]
    if source_id not in sources:
        sources.append(source_id)

    existing.update(
        {
            "id": key,
            "event_id": event_id,
            "occurrence": occurrence,
            "knowledge_type": "REPORTED",
            "source_npc_ids": sources,
            "room_id": getattr(source.location.db, "room_id", None),
            "room_name": source.location.key,
            "last_heard_at": now,
            "heard_count": int(existing.get("heard_count", 0) or 0) + 1,
            "event_archived": str(event.get("status") or "").lower() == "historical",
            "canon_status": "prototype",
        }
    )

    if better_route:
        existing["source_npc_id"] = source_id
        existing["source_name"] = source.key
        existing["source_via"] = source_route.get("via")
        existing["origin_npc_id"] = str(origin_npc_id or source_id)
        existing["hops"] = candidate_hops
    elif existing_hops is not None:
        existing["hops"] = existing_hops

    if created:
        existing["first_learned_at"] = now

    records[key] = existing
    target.db.event_information = records

    action_consequence = _emit_information_shared_action(
        source,
        target,
        event_id,
        occurrence,
        source_route.get("via"),
        candidate_hops,
        existing.get("hops"),
        existing.get("heard_count"),
        created,
        existing,
    )

    return {
        "success": True,
        "created": created,
        "reason": "INFORMATION_SHARED",
        "event_id": event_id,
        "occurrence": occurrence,
        "source_npc_id": source_id,
        "source_name": source.key,
        "target_npc_id": target_id,
        "target_name": target.key,
        "source_via": source_route.get("via"),
        "candidate_hops": candidate_hops,
        "hops": existing.get("hops"),
        "heard_count": existing.get("heard_count"),
        "event_archived": existing.get("event_archived"),
        "site": site.key if site else None,
        "action_consequence": action_consequence,
        "record": existing,
    }


def inspect_event_information(npc):
    rows = list(event_information_records(npc).values())
    rows.sort(key=lambda row: (str(row.get("event_id") or ""), int(row.get("occurrence", 0) or 0)))
    return {
        "build": INFORMATION_BUILD,
        "npc": npc.key if npc else None,
        "npc_id": _npc_id(npc),
        "records": rows,
    }
