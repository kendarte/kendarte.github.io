from datetime import datetime, timezone

from evennia import search_tag


RELATIONSHIP_BUILD = "0.20.0-relationship-obligations"
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
    if not wanted:
        return None
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, "npc_id", "") or "") == wanted:
            return obj
    return None


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


def collect_relationship_candidates(npc, default_priority=50):
    """Derive persistent RELATIONSHIP goals that dynamically follow another NPC."""
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
            try:
                priority = int(obligation.get("priority", default_priority))
            except (TypeError, ValueError):
                priority = int(default_priority)

            output.append(
                {
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
                    "relationship_kind": obligation.get("kind") or "OBLIGATION",
                }
            )

    return output


def resolve_relationship_goal(npc, obligation_id, target_npc_id):
    """Resolve one obligation only when actor and target NPC physically coincide."""
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
    relation["target_npc_id"] = target_id
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
    for target_id, raw_relation in _relationships(npc).items():
        relation = _relation_record(raw_relation)
        target = _npc_by_id(target_id)
        rows.append(
            {
                "target_npc_id": str(target_id),
                "target_name": target.key if target else relation.get("target_name"),
                "target_location": target.location.key if target and target.location else None,
                "relation": relation,
                "obligations": _obligations(relation),
            }
        )
    return rows
