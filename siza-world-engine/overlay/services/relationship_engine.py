from datetime import datetime, timezone

from evennia import search_object
from services.actor_registry import find_npc_by_id
from services.social_graph_engine import peek_social_entity_id, resolve_social_entity, sync_legacy_relationships

from services.information_engine import (
    event_knowledge_route,
    find_event_occurrence,
    share_event_information,
)


RELATIONSHIP_BUILD = "0.35.0-social-information-action"
FACT_SHARE_RELATIONSHIP_BUILD = "0.89.0-social-fact-share-obligation"


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
    return find_npc_by_id(wanted)


def _target_key(target):
    identity = peek_social_entity_id(target)
    return identity[4:] if identity and identity.startswith("NPC:") else identity


def _resolve_target(identity):
    text = str(identity or "").strip()
    return resolve_social_entity(text) if text.startswith(("NPC:", "PLAYER:")) else (_npc_by_id(text) or _dbref_target(text))


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


def _fact_share_obligation_ready(npc, obligation):
    fact_id = str((obligation or {}).get("fact_id") or "").strip()
    if not npc or not fact_id:
        return False, None
    from services.knowledge_context_engine import fact_knowledge_state
    from services.knowledge_fact_engine import find_knowledge_fact

    fact = find_knowledge_fact(npc, fact_id)
    if not fact:
        return False, None
    return bool(fact_knowledge_state(npc, fact).get("known")), fact


def collect_relationship_candidates(npc, default_priority=50):
    """Derive persistent social goals that dynamically follow another NPC."""
    if not npc or not bool(npc.db.decision_enabled):
        return []

    output = []
    for target_npc_id, raw_relation in _relationships(npc).items():
        relation = _relation_record(raw_relation)
        target_social_id = str(relation.get("target_social_entity_id") or target_npc_id)
        target = _resolve_target(target_social_id)
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
            elif kind == "SHARE_FACT":
                ready, _fact = _fact_share_obligation_ready(npc, obligation)
                if not ready:
                    continue
            try:
                priority = int(obligation.get("priority", default_priority))
            except (TypeError, ValueError):
                priority = int(default_priority)

            candidate = {
                "id": f"RELATIONSHIP:{obligation_id}",
                "relationship_obligation_id": obligation_id,
                "relationship_target_npc_id": str(relation.get("target_npc_id") or "") or None,
                "target_social_entity_id": peek_social_entity_id(target),
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
            elif kind == "SHARE_FACT":
                candidate["fact_id"] = obligation.get("fact_id")
            output.append(candidate)

    return output


def create_information_obligation(source, target, event_id, occurrence, priority):
    """Create or reactivate one explicit social intent to tell a target about a known occurrence."""
    if not source or not target:
        return {"success": False, "reason": "BAD_NPC"}
    source_id = str(getattr(source.db, "npc_id", "") or "").strip()
    target_id, target_social_id = _target_key(target), peek_social_entity_id(target)
    if not source_id or not target_id or not target_social_id or target_social_id == peek_social_entity_id(source):
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
    relation["target_type"] = "NPC" if target_social_id.startswith("NPC:") else "PLAYER"
    relation["target_social_entity_id"] = target_social_id
    if target_social_id.startswith("NPC:"):
        relation["target_npc_id"] = target_id
    relation["target_dbref"] = int(target.id)
    relation["target_name"] = target.key
    relationships[target_id] = relation
    source.db.relationships = relationships
    sync_legacy_relationships(source)

    return {
        "success": True,
        "created": created,
        "obligation_id": obligation_id,
        "source_npc_id": source_id,
        "source_name": source.key,
        "target_npc_id": target_id if target_social_id.startswith("NPC:") else None,
        "target_social_entity_id": target_social_id,
        "target_name": target.key,
        "event_id": str(event_id).strip(),
        "occurrence": occurrence,
        "priority": priority,
        "source_via": route.get("via"),
        "site": site.key if site else None,
    }


def create_fact_share_obligation(source, target, fact_id, priority=50):
    """Create or reactivate a social intent to share one exact Fact with a target NPC."""
    if not source or not target:
        return {"success": False, "reason": "BAD_NPC"}
    source_id = str(getattr(source.db, "npc_id", "") or "").strip()
    target_id, target_social_id = _target_key(target), peek_social_entity_id(target)
    wanted_fact_id = str(fact_id or "").strip()
    if not source_id or not target_id or not target_social_id or target_social_id == peek_social_entity_id(source) or not wanted_fact_id:
        return {"success": False, "reason": "BAD_NPC_OR_FACT"}
    try:
        priority = int(priority)
    except (TypeError, ValueError):
        return {"success": False, "reason": "BAD_NUMBER"}

    ready, fact = _fact_share_obligation_ready(source, {"fact_id": wanted_fact_id})
    if not fact:
        return {"success": False, "reason": "SOURCE_FACT_NOT_FOUND", "fact_id": wanted_fact_id}
    if not ready:
        return {"success": False, "reason": "SOURCE_DOES_NOT_KNOW_FACT", "fact_id": wanted_fact_id}

    relationships = _relationships(source)
    relation = _relation_record(relationships.get(target_id))
    obligations = _obligations(relation)
    obligation_id = f"SHARE-FACT-{target_id}-{wanted_fact_id}"
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "id": obligation_id,
        "kind": "SHARE_FACT",
        "active": True,
        "status": "pending",
        "priority": priority,
        "one_shot": True,
        "fact_id": wanted_fact_id,
        "activity": f"buscando a {target.key} para compartir un dato conocido",
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
    relation["target_type"] = "NPC" if target_social_id.startswith("NPC:") else "PLAYER"
    relation["target_social_entity_id"] = target_social_id
    if target_social_id.startswith("NPC:"):
        relation["target_npc_id"] = target_id
    relation["target_dbref"] = int(target.id)
    relation["target_name"] = target.key
    relationships[target_id] = relation
    source.db.relationships = relationships
    sync_legacy_relationships(source)

    return {
        "success": True,
        "created": created,
        "obligation_id": obligation_id,
        "source_npc_id": source_id,
        "source_name": source.key,
        "target_npc_id": target_id if target_social_id.startswith("NPC:") else None,
        "target_social_entity_id": target_social_id,
        "target_name": target.key,
        "fact_id": wanted_fact_id,
        "fact_topic": fact.get("topic"),
        "priority": priority,
        "build": FACT_SHARE_RELATIONSHIP_BUILD,
    }


def resolve_relationship_goal(npc, obligation_id, target_npc_id=None, target_social_entity_id=None):
    """Resolve a goal against any social actor physically in the same room."""
    if not npc:
        return {"completed": False, "resolved": False, "reason": "NO_NPC"}

    wanted = str(obligation_id or "").strip()
    target_id = str(target_social_entity_id or target_npc_id or "").strip()
    target = _resolve_target(target_id)
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
    relation_key = _target_key(target)
    relation = _relation_record(relationships.get(relation_key))
    obligations = _obligations(relation)
    changed = False
    now = datetime.now(timezone.utc).isoformat()
    information_result = None
    fact_transfer_result = None
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
        elif relationship_kind == "SHARE_FACT":
            from services.knowledge_fact_transfer_engine import transfer_knowledge_fact

            fact_transfer_result = transfer_knowledge_fact(
                npc,
                target,
                obligation.get("fact_id"),
            )
            if not fact_transfer_result.get("success"):
                return {
                    "completed": False,
                    "resolved": False,
                    "reason": fact_transfer_result.get("reason") or "FACT_TRANSFER_FAILED",
                    "obligation_id": wanted,
                    "target_npc_id": target_id,
                    "target_name": target.key,
                    "relationship_kind": relationship_kind,
                    "fact_shared": False,
                    "fact_transfer_result": fact_transfer_result,
                }
            obligation["fact_transfer_result"] = {
                "fact_id": fact_transfer_result.get("fact_id"),
                "transfer_id": fact_transfer_result.get("transfer_id"),
                "created": fact_transfer_result.get("created"),
                "reason": fact_transfer_result.get("reason"),
                "knowledge_after": fact_transfer_result.get("knowledge_after"),
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
    relation["target_type"] = "NPC" if bool(getattr(target.db, "is_npc", False)) else "PLAYER"
    relation["target_social_entity_id"] = peek_social_entity_id(target)
    if bool(getattr(target.db, "is_npc", False)):
        relation["target_npc_id"] = relation_key
    relation["target_dbref"] = int(target.id)
    relation["target_name"] = target.key
    relation["last_interaction_at"] = now
    relationships[relation_key] = relation
    npc.db.relationships = relationships
    sync_legacy_relationships(npc)

    return {
        "completed": True,
        "resolved": True,
        "reason": "RESOLVED",
        "obligation_id": wanted,
        "target_npc_id": relation.get("target_npc_id"),
        "target_social_entity_id": peek_social_entity_id(target),
        "target_name": target.key,
        "location": npc.location.key if npc.location else None,
        "relationship_kind": relationship_kind,
        "information_shared": bool(information_result and information_result.get("success")),
        "information_result": information_result,
        "fact_shared": bool(fact_transfer_result and fact_transfer_result.get("success")),
        "fact_transfer_result": fact_transfer_result,
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
            sync_legacy_relationships(npc)
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
