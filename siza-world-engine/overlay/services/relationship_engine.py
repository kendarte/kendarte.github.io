from datetime import datetime, timezone

from evennia import search_object, search_tag

from services.information_engine import (
    event_knowledge_route,
    find_event_occurrence,
    share_event_information,
)


RELATIONSHIP_BUILD = "0.35.0-social-information-action"
ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _plain_dict(value):
    try:
        return dict(value or {})
    except Exception:
        return {}


def _record(value):
    try:
        return {str(key): item for key, item in value.items()}
    except Exception:
        return None


def _npc_by_id(npc_id):
    wanted = str(npc_id or "").strip()
    if not wanted or wanted.startswith("DBREF:"):
        return None
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, "npc_id", "") or "") == wanted:
            return obj
    return None


def _dbref_target(identity):
    text = str(identity or "").strip()
    if not text.startswith("DBREF:"):
        return None
    raw = text.split(":", 1)[1].strip()
    if not raw.isdigit():
        return None
    matches = list(search_object(f"#{raw}"))
    return matches[0] if len(matches) == 1 else None


def _relationships(npc):
    return _plain_dict(getattr(npc.db, "relationships", {})) if npc else {}


def _relation_record(raw):
    relation = _record(raw)
    return relation if relation is not None else {}


def _obligations(relation):
    output = []
    for raw in _plain_list((relation or {}).get("obligations")):
        item = _record(raw)
        if item is not None:
            output.append(item)
    return output


def _information_obligation_ready(npc, obligation):
    event_id = str((obligation or {}).get("event_id") or "").strip()
    occurrence = (obligation or {}).get("occurrence")
    if not event_id or occurrence is None:
        return False, None, None
    site, event = find_event_occurrence(event_id, occurrence=occurrence)
    if not event:
        return False, site, event
    return bool(event_knowledge_route(npc, event).get("known")), site, event


def collect_relationship_candidates(npc, default_priority=50):
    """Derive persistent social goals that dynamically follow another NPC."""
    if not npc or not bool(npc.db.decision_enabled):
        return []

    output = []
    for target_npc_id, raw_relation in _relationships(npc).items():
        relation = _relation_record(raw_relation)
        target = _npc_by_id(target_npc_id)
        if not target or not target.location:
            continue

        for obligation in _obligations(relation):
            if not bool(obligation.get("active", False)):
                continue
            status = str(obligation.get("status") or "pending").lower()
            if status not in {"pending", "active", "in_progress"}:
                continue

            obligation_id = str(obligation.get("id") or "").strip()
            if not obligation_id:
                continue
            kind = str(obligation.get("kind") or "OBLIGATION").upper()
            if kind == "INFORM":
                ready, _site, _event = _information_obligation_ready(npc, obligation)
                if not ready:
                    continue
            try:
                priority = int(obligation.get("priority", default_priority))
            except (TypeError, ValueError):
                priority = int(default_priority)

            candidate = {
                "id": f"RELATIONSHIP:{obligation_id}",
                "relationship_obligation_id": obligation_id,
                "relationship_target_npc_id": str(target_npc_id),
                "relationship_target_name": target.key,
                "type": "RELATIONSHIP",
                "priority": priority,
                "active": True,
                "target_room_id": getattr(target.location.db, "room_id", None),
                "target_room_key": target.location.key,
                "activity": obligation.get("activity") or f"atendiendo un asunto con {target.key}",
                "source": "RELATIONSHIP",
                "one_shot": bool(obligation.get("one_shot", True)),
                "canon_status": obligation.get("canon_status") or "prototype",
                "relationship_kind": kind,
            }
            if kind == "INFORM":
                candidate.update(
                    {
                        "information_event_id": obligation.get("event_id"),
                        "information_occurrence": obligation.get("occurrence"),
                    }
                )
            output.append(candidate)

    return output


def create_information_obligation(source, target, event_id, occurrence, priority):
    """Create or reactivate one explicit social intent to tell a target about a known occurrence."""
    if not source or not target:
        return {"success": False, "reason": "BAD_NPC"}
    source_id = str(getattr(source.db, "npc_id", "") or "").strip()
    target_id = str(getattr(target.db, "npc_id", "") or "").strip()
    if not source_id or not target_id or source_id == target_id:
        return {"success": False, "reason": "BAD_NPC"}
    try:
        occurrence = int(occurrence)
        priority = int(priority)
    except (TypeError, ValueError):
        return {"success": False, "reason": "BAD_NUMBER"}

    site, event = find_event_occurrence(event_id, occurrence=occurrence)
    if not event:
        return {"success": False, "reason": "EVENT_NOT_FOUND"}
    route = event_knowledge_route(source, event)
    if not route.get("known"):
        return {"success": False, "reason": "SOURCE_NOT_AWARE"}

    relationships = _relationships(source)
    relation = _relation_record(relationships.get(target_id))
    obligations = _obligations(relation)
    obligation_id = f"INFORM-{target_id}-{str(event_id).strip()}-{occurrence}"
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "id": obligation_id,
        "kind": "INFORM",
        "active": True,
        "status": "pending",
        "priority": priority,
        "one_shot": True,
        "event_id": str(event_id).strip(),
        "occurrence": occurrence,
        "activity": f"contándole a {target.key} sobre {str(event_id).strip()} occurrence {occurrence}",
        "activated_at": now,
        "canon_status": "prototype",
    }

    created = True
    for index, existing in enumerate(obligations):
        if str(existing.get("id") or "") != obligation_id:
            continue
        payload["created_at"] = existing.get("created_at") or now
        obligations[index] = payload
        created = False
        break
    if created:
        payload["created_at"] = now
        obligations.append(payload)

    relation["obligations"] = obligations
    relation["target_type"] = "NPC"
    relation["target_npc_id"] = target_id
    relation["target_dbref"] = int(target.id)
    relation["target_name"] = target.key
    relationships[target_id] = relation
    source.db.relationships = relationships

    return {
        "success": True,
        "created": created,
        "obligation_id": obligation_id,
        "source_npc_id": source_id,
        "source_name": source.key,
        "target_npc_id": target_id,
        "target_name": target.key,
        "event_id": str(event_id).strip(),
        "occurrence": occurrence,
        "priority": priority,
        "source_via": route.get("via"),
        "site": site.key if site else None,
    }


def resolve_relationship_goal(npc, obligation_id, target_npc_id):
    """Resolve one social obligation only when actor and target NPC physically coincide."""
    if not npc:
        return {"completed": False, "resolved": False, "reason": "NO_NPC"}

    wanted = str(obligation_id or "").strip()
    target_id = str(target_npc_id or "").strip()
    target = _npc_by_id(target_id)
    if not wanted or not target:
        return {"completed": False, "resolved": False, "reason": "BAD_TARGET"}
    if not npc.location or npc.location != target.location:
        return {
            "completed": False,
            "resolved": False,
            "reason": "TARGET_MOVED",
            "target_npc_id": target_id,
            "target_name": target.key,
        }

    relationships = _relationships(npc)
    relation = _relation_record(relationships.get(target_id))
    obligations = _obligations(relation)
    changed = False
    now = datetime.now(timezone.utc).isoformat()
    information_result = None
    relationship_kind = None

    for index, obligation in enumerate(obligations):
        if str(obligation.get("id") or "") != wanted:
            continue
        if not bool(obligation.get("active", False)):
            return {
                "completed": False,
                "resolved": False,
                "reason": "OBLIGATION_INACTIVE",
                "obligation_id": wanted,
                "target_npc_id": target_id,
                "target_name": target.key,
            }

        relationship_kind = str(obligation.get("kind") or "OBLIGATION").upper()
        if relationship_kind == "INFORM":
            information_result = share_event_information(
                npc,
                target,
                obligation.get("event_id"),
                occurrence=obligation.get("occurrence"),
            )
            if not information_result.get("success"):
                return {
                    "completed": False,
                    "resolved": False,
                    "reason": information_result.get("reason") or "INFORMATION_FAILED",
                    "obligation_id": wanted,
                    "target_npc_id": target_id,
                    "target_name": target.key,
                    "relationship_kind": relationship_kind,
                    "information_shared": False,
                    "information_result": information_result,
                }
            obligation["information_result"] = {
                "event_id": information_result.get("event_id"),
                "occurrence": information_result.get("occurrence"),
                "created": information_result.get("created"),
                "source_via": information_result.get("source_via"),
                "candidate_hops": information_result.get("candidate_hops"),
                "hops": information_result.get("hops"),
                "heard_count": information_result.get("heard_count"),
            }

        obligation["active"] = False
        obligation["status"] = "completed"
        obligation["completed_at"] = now
        obligation["completed_with_npc_id"] = target_id
        obligation["completed_with_name"] = target.key
        obligations[index] = obligation
        changed = True
        break

    if not changed:
        return {
            "completed": False,
            "resolved": False,
            "reason": "OBLIGATION_NOT_FOUND",
            "obligation_id": wanted,
            "target_npc_id": target_id,
            "target_name": target.key,
        }

    relation["obligations"] = obligations
    relation["target_type"] = "NPC"
    relation["target_npc_id"] = target_id
    relation["target_dbref"] = int(target.id)
    relation["target_name"] = target.key
    relation["last_interaction_at"] = now
    relationships[target_id] = relation
    npc.db.relationships = relationships

    return {
        "completed": True,
        "resolved": True,
        "reason": "RESOLVED",
        "obligation_id": wanted,
        "target_npc_id": target_id,
        "target_name": target.key,
        "location": npc.location.key if npc.location else None,
        "relationship_kind": relationship_kind,
        "information_shared": bool(information_result and information_result.get("success")),
        "information_result": information_result,
    }


def set_relationship_obligation_active(npc, obligation_id, active):
    """Admin/debug activation preserving authored relationship structure."""
    if not npc:
        return None
    wanted = str(obligation_id or "").strip()
    relationships = _relationships(npc)
    now = datetime.now(timezone.utc).isoformat()

    for target_id, raw_relation in list(relationships.items()):
        relation = _relation_record(raw_relation)
        obligations = _obligations(relation)
        for index, obligation in enumerate(obligations):
            if str(obligation.get("id") or "") != wanted:
                continue
            desired = bool(active)
            obligation["active"] = desired
            obligation["status"] = "pending" if desired else "inactive"
            if desired:
                obligation["activated_at"] = now
                obligation.pop("completed_at", None)
                obligation.pop("completed_with_npc_id", None)
                obligation.pop("completed_with_name", None)
            else:
                obligation["deactivated_at"] = now
            obligations[index] = obligation
            relation["obligations"] = obligations
            relationships[str(target_id)] = relation
            npc.db.relationships = relationships
            return {
                "npc": npc,
                "target_npc_id": str(target_id),
                "obligation_id": wanted,
                "active": desired,
                "status": obligation.get("status"),
            }
    return None


def inspect_relationships(npc):
    rows = []
    if not npc:
        return rows
    for identity, raw_relation in _relationships(npc).items():
        relation = _relation_record(raw_relation)
        npc_target = _npc_by_id(identity)
        dbref_target = _dbref_target(identity)
        target = npc_target or dbref_target
        target_type = str(
            relation.get("target_type")
            or ("NPC" if npc_target else "CHARACTER" if str(identity).startswith("DBREF:") else "UNKNOWN")
        ).upper()
        target_npc_id = relation.get("target_npc_id") or (str(identity) if npc_target else None)
        target_dbref = relation.get("target_dbref")
        if target_dbref is None and dbref_target:
            target_dbref = int(dbref_target.id)
        rows.append(
            {
                "identity": str(identity),
                "target_type": target_type,
                "target_npc_id": target_npc_id,
                "target_dbref": target_dbref,
                "target_name": target.key if target else relation.get("target_name") or relation.get("name"),
                "target_location": target.location.key if target and target.location else None,
                "relation": relation,
                "obligations": _obligations(relation),
            }
        )
    return rows
