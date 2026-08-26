from copy import deepcopy

from services.action_intent_proposal_engine import build_local_capability_catalog
from services.knowledge_fact_retrieval_engine import retrieve_known_facts
from services.object_action_engine import authored_object_actions
from services.worldbook_local_retrieval import retrieve_worldbook_context


DM_CONTEXT_BROKER_BUILD = "dm-0.1-bounded-context-broker"
MAX_ENGINE_RESULTS = 12
MAX_NPC_FACT_HOLDERS = 6
MAX_FACTS_PER_HOLDER = 2

_CONTEXT_NEED_QUERY_MAP = {
    "WORLD_OBJECT_STATE": ("local_object_state",),
    "TARGET_STATE": ("local_npc_state",),
    "KNOWLEDGE": ("local_entities_with_relevant_knowledge",),
    "RELATIONSHIP": ("local_relationship_context",),
    "FACTION_AUTHORITY": ("local_authority_context",),
    "LOCATION_TOPOLOGY": ("local_route_objects_and_exits",),
    "EVENT_STATE": ("active_local_events",),
    "INVENTORY": ("inventory",),
}


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


def _local_objects(actor):
    site = getattr(actor, "location", None) if actor else None
    return [
        obj for obj in list(getattr(site, "contents", []) or [])
        if obj is not actor and not getattr(obj, "destination", None) and not bool(getattr(obj.db, "hidden", False))
    ] if site else []


def _safe_scalar(value):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:240]
    return str(value)[:240]


def _safe_state(value, max_fields=16):
    output = {}
    for key, item in list(_plain_dict(value).items())[:max_fields]:
        if isinstance(item, dict):
            output[str(key)] = {str(k): _safe_scalar(v) for k, v in list(_plain_dict(item).items())[:8]}
        elif isinstance(item, (list, tuple)):
            output[str(key)] = [_safe_scalar(v) for v in list(item)[:8]]
        else:
            output[str(key)] = _safe_scalar(item)
    return output


def _entity_ref(obj):
    if not obj or getattr(obj, "id", None) is None:
        return None
    return f"DBREF:{int(obj.id)}"


def _entity_summary(obj, include_state=False):
    row = {
        "ref": _entity_ref(obj),
        "name": str(getattr(obj, "key", "")),
        "kind": "NPC" if bool(getattr(obj.db, "is_npc", False)) else "OBJECT",
        "npc_id": str(getattr(obj.db, "npc_id", "") or "") or None,
        "object_id": str(getattr(obj.db, "object_id", "") or "") or None,
        "portable": bool(getattr(obj.db, "portable", False)),
    }
    if include_state:
        row["state"] = _safe_state(getattr(obj.db, "state", {}))
    return row


def _fact_holders(actor, query):
    holders = []
    candidates = [actor] + [obj for obj in _local_objects(actor) if bool(getattr(obj.db, "is_npc", False))]
    for entity in candidates[:MAX_NPC_FACT_HOLDERS + 1]:
        packet = retrieve_known_facts(
            entity,
            query=query,
            max_facts=MAX_FACTS_PER_HOLDER,
            char_budget=600,
        )
        selected = []
        for fact in _plain_list(packet.get("selected")):
            row = _plain_dict(fact)
            selected.append({
                "id": str(row.get("id") or ""),
                "topic": str(row.get("topic") or ""),
                "text": str(row.get("text") or ""),
                "canon_status": row.get("canon_status"),
            })
        if not selected:
            continue
        holders.append({
            "holder_ref": "SELF" if entity is actor else _entity_ref(entity),
            "holder_name": str(getattr(entity, "key", "")),
            "holder_kind": "PLAYER" if entity is actor else "NPC",
            "facts": selected,
        })
    return holders


def _visible_objects(actor, include_state=False):
    output = []
    for obj in _local_objects(actor):
        if bool(getattr(obj.db, "is_npc", False)):
            continue
        row = _entity_summary(obj, include_state=include_state)
        row["actions"] = [
            {
                "id": str(action.get("id") or ""),
                "name": str(action.get("name") or action.get("id") or ""),
                "enabled": bool(action.get("enabled", True)),
                "canon_status": action.get("canon_status"),
            }
            for action in authored_object_actions(obj)[:8]
        ]
        output.append(row)
    return output


def _local_npc_state(actor):
    return [
        _entity_summary(obj, include_state=True)
        for obj in _local_objects(actor)
        if bool(getattr(obj.db, "is_npc", False))
    ]


def _relationship_context(actor):
    output = []
    local = [actor] + [obj for obj in _local_objects(actor) if bool(getattr(obj.db, "is_npc", False))]
    for entity in local:
        relationships = _plain_dict(getattr(entity.db, "relationships", {}))
        if not relationships:
            continue
        rows = []
        for target, raw in list(relationships.items())[:8]:
            relation = _plain_dict(raw)
            rows.append({
                "target": str(target),
                "familiarity": relation.get("familiarity"),
                "status": relation.get("status"),
                "type": relation.get("type") or relation.get("relationship_type"),
                "obligation_count": len(_plain_list(relation.get("obligations"))),
            })
        output.append({
            "holder_ref": "SELF" if entity is actor else _entity_ref(entity),
            "holder_name": str(getattr(entity, "key", "")),
            "relationships": rows,
        })
    return output


def _authority_context(actor):
    output = []
    site = getattr(actor, "location", None) if actor else None
    candidates = ([site] if site else []) + _local_objects(actor)
    fields = ("faction_id", "faction", "authority", "institution", "role", "job_id")
    for entity in candidates:
        authored = {}
        for field in fields:
            value = getattr(entity.db, field, None)
            if value not in (None, "", [], {}):
                authored[field] = _safe_scalar(value)
        if authored:
            output.append({
                "ref": "ROOM" if entity is site else _entity_ref(entity),
                "name": str(getattr(entity, "key", "")),
                "authored": authored,
            })
    return output


def _route_context(actor, snapshot):
    return {
        "location": deepcopy(_plain_dict(snapshot).get("location")),
        "exits": deepcopy(_plain_list(_plain_dict(snapshot).get("local_exits"))),
        "visible_objects": _visible_objects(actor, include_state=False),
    }


def _hazard_context(actor, snapshot):
    site = getattr(actor, "location", None) if actor else None
    return {
        "active_local_events": deepcopy(_plain_list(_plain_dict(snapshot).get("active_local_events"))),
        "world_context_tags": list(getattr(getattr(site, "db", None), "world_context_tags", []) or [])[:12] if site else [],
        "combat_modifiers": deepcopy(list(getattr(getattr(site, "db", None), "combat_modifiers", []) or [])[:12]) if site else [],
    }


def _resolve_engine_query(query_id, actor, raw_player_input, snapshot, search_query):
    query = str(query_id or "").strip()
    if query in {"local_entities_with_relevant_knowledge", "npcs_with_route_or_access_knowledge", "player_active_facts_supporting_route_inference", "active_facts_related_to_campaign_lead"}:
        return {"status": "RESOLVED", "data": _fact_holders(actor, search_query)}
    if query in {"visible_documents_or_objects_with_relevant_information", "objects_or_documents_that_can_change_route_options", "local_object_state"}:
        return {"status": "RESOLVED", "data": _visible_objects(actor, include_state=True)}
    if query in {"active_local_events", "time_sensitive_local_events", "world_consequences_already_created_by_player_actions"}:
        return {"status": "RESOLVED", "data": deepcopy(_plain_list(snapshot.get("active_local_events")))}
    if query in {"local_route_objects_and_exits", "alternative_local_capabilities", "nearby_shelter_resources_allies_or_alternate_paths"}:
        data = _route_context(actor, snapshot)
        if query == "alternative_local_capabilities":
            data["capabilities"] = deepcopy(build_local_capability_catalog(actor))[:MAX_ENGINE_RESULTS]
        return {"status": "RESOLVED", "data": data}
    if query in {"relationships_or_factions_that_can_change_access", "local_relationship_context"}:
        return {"status": "RESOLVED", "data": _relationship_context(actor)}
    if query in {"affected_npcs_factions_and_authorities", "local_owners_or_authorities_of_required_resources", "local_authority_context"}:
        return {"status": "RESOLVED", "data": _authority_context(actor)}
    if query in {"current_route_hazards", "active_world_events_on_or_near_route", "combat_eligible_hostile_or_opposed_actors"}:
        data = _hazard_context(actor, snapshot)
        if query == "combat_eligible_hostile_or_opposed_actors":
            data["local_npcs"] = _local_npc_state(actor)
        return {"status": "RESOLVED", "data": data}
    if query == "local_npc_state":
        return {"status": "RESOLVED", "data": _local_npc_state(actor)}
    if query == "inventory":
        return {"status": "RESOLVED", "data": deepcopy(_plain_list(snapshot.get("inventory")))}
    if query in {"required_resources_for_current_route", "resource_availability_changes"}:
        return {"status": "RESOLVED", "data": _visible_objects(actor, include_state=True)}
    if query in {"authoritative_campaign_climax_state", "present_entities_objects_facts_and_events_relevant_to_final_resolution"}:
        return {
            "status": "RESOLVED",
            "data": {
                "location": deepcopy(_plain_dict(snapshot.get("location"))),
                "events": deepcopy(_plain_list(snapshot.get("active_local_events"))),
                "facts": _fact_holders(actor, search_query),
                "entities": [_entity_summary(obj, include_state=True) for obj in _local_objects(actor)][:MAX_ENGINE_RESULTS],
            },
        }
    return {"status": "UNSUPPORTED_QUERY", "data": None}


def _unique_strings(values):
    output = []
    for value in list(values or []):
        text = str(value or "").strip()
        if text and text not in output:
            output.append(text)
    return output


def build_dm_context_packet(actor, raw_player_input, dm_plan, world_snapshot, context_needs=None, *, worldbook_chunks_dir=None):
    """Resolve allowlisted, read-only context requests for one DM turn. No result mutates world or player Knowledge."""
    plan = _plain_dict(dm_plan)
    snapshot = _plain_dict(world_snapshot)
    requests = _plain_dict(plan.get("retrieval_requests"))
    engine_queries = _unique_strings(requests.get("world_engine"))
    worldbook_topics = _unique_strings(requests.get("world_book"))
    needs = _unique_strings(context_needs)

    for need in needs:
        for query in _CONTEXT_NEED_QUERY_MAP.get(need, ()):
            if query not in engine_queries:
                engine_queries.append(query)
    if "WORLD_BOOK_CANON" in needs and not worldbook_topics:
        worldbook_topics.append(str(raw_player_input or "").strip())

    search_query = " ".join(_unique_strings([raw_player_input, *worldbook_topics]))[:700]
    engine_results = []
    for query in engine_queries[:MAX_ENGINE_RESULTS]:
        resolved = _resolve_engine_query(query, actor, raw_player_input, snapshot, search_query)
        engine_results.append({
            "query": query,
            "status": resolved.get("status"),
            "data": resolved.get("data"),
        })

    wb_queries = _unique_strings([*worldbook_topics, raw_player_input])
    worldbook = retrieve_worldbook_context(
        wb_queries,
        chunks_dir=worldbook_chunks_dir,
        max_snippets=4,
        char_budget=2200,
    ) if wb_queries else {
        "status": "NO_QUERY",
        "available": False,
        "snippets": [],
        "authority": "DM_CONTEXT_ONLY",
        "player_knowledge": False,
    }

    return {
        "status": "CONTEXT_READY",
        "engine_queries": engine_queries,
        "worldbook_topics": worldbook_topics,
        "context_needs": needs,
        "world_engine": engine_results,
        "world_book": {
            "status": worldbook.get("status"),
            "available": worldbook.get("available"),
            "queries": worldbook.get("queries"),
            "snippets": deepcopy(_plain_list(worldbook.get("snippets"))),
            "used_chars": worldbook.get("used_chars"),
            "authority": "DM_CONTEXT_ONLY",
            "player_knowledge": False,
        },
        "authority": {
            "read_only": True,
            "dm_only": True,
            "mutates_world": False,
            "creates_facts": False,
            "grants_player_knowledge": False,
            "executes_actions": False,
        },
        "build": DM_CONTEXT_BROKER_BUILD,
    }


def augment_dm_world_snapshot(world_snapshot, context_packet):
    snapshot = deepcopy(_plain_dict(world_snapshot))
    snapshot["dm_context"] = deepcopy(_plain_dict(context_packet))
    return snapshot
