from datetime import datetime, timezone

from services.knowledge_context_engine import (
    FACT_LIFECYCLE_BUILD,
    FACT_STATUS_ACTIVE,
    FACT_STATUS_RETRACTED,
    FACT_STATUS_SUPERSEDED,
    knowledge_facts,
)


KNOWLEDGE_FACT_BUILD = "0.57.0-persistent-knowledge-facts"
FACT_LIFECYCLE_HISTORY_LIMIT = 25
_ALLOWED_FACT_STATUSES = {
    FACT_STATUS_ACTIVE,
    FACT_STATUS_RETRACTED,
    FACT_STATUS_SUPERSEDED,
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


def _record(value):
    try:
        return {str(key): item for key, item in value.items()}
    except Exception:
        return None


def _normalized_fact_status(value):
    return str(value or FACT_STATUS_ACTIVE).strip().upper()


def upsert_knowledge_fact(entity, fact, action=None):
    """Persist one structured Knowledge Fact on any Character/NPC, idempotent by fact id."""
    if not entity:
        return {"status": "NO_ENTITY", "build": KNOWLEDGE_FACT_BUILD}

    item = _record(fact)
    fact_id = str((item or {}).get("id") or "").strip()
    if not fact_id:
        return {"status": "BAD_FACT", "build": KNOWLEDGE_FACT_BUILD}

    explicit_fact_status = "fact_status" in item
    item["id"] = fact_id
    item.setdefault("topic", fact_id)
    item.setdefault("text", "")
    item.setdefault("canon_status", "prototype")
    try:
        item["required_level"] = max(0, int(item.get("required_level", 1) or 1))
    except (TypeError, ValueError):
        item["required_level"] = 1
    item["source"] = _plain_dict(item.get("source"))
    item["learned_by"] = _plain_dict(item.get("learned_by"))

    packet = _plain_dict(action)
    if packet:
        learned_by = dict(item.get("learned_by") or {})
        learned_by.setdefault("action_id", packet.get("action_id"))
        learned_by.setdefault("object_action_id", packet.get("object_action_id"))
        learned_by.setdefault("attempt_id", packet.get("attempt_id"))
        learned_by.setdefault("provider", packet.get("provider"))
        learned_by.setdefault("outcome", packet.get("outcome"))
        item["learned_by"] = learned_by

        source = dict(item.get("source") or {})
        source.setdefault("object_id", packet.get("object_id"))
        source.setdefault("object_dbref", packet.get("object_dbref"))
        source.setdefault("object_name", packet.get("object_name"))
        source.setdefault("site_room_id", packet.get("site_room_id"))
        source.setdefault("site_dbref", packet.get("site_dbref"))
        source.setdefault("site_name", packet.get("site_name"))
        item["source"] = source

    rows = []
    created = True
    existing_learned_at = None
    existing_status = None
    existing_status_changed_at = None
    existing_status_reason = None
    existing_superseded_by = None
    existing_lifecycle_history = []
    for raw in _plain_list(getattr(entity.db, "knowledge_facts", [])):
        current = _record(raw)
        if current is None:
            continue
        if str(current.get("id") or "") != fact_id:
            rows.append(current)
            continue
        created = False
        existing_learned_at = current.get("learned_at")
        existing_status = current.get("fact_status")
        existing_status_changed_at = current.get("fact_status_changed_at")
        existing_status_reason = current.get("fact_status_reason")
        existing_superseded_by = current.get("superseded_by_fact_id")
        existing_lifecycle_history = _plain_list(current.get("fact_lifecycle_history"))

    if explicit_fact_status:
        item["fact_status"] = _normalized_fact_status(item.get("fact_status"))
    else:
        item["fact_status"] = _normalized_fact_status(existing_status or FACT_STATUS_ACTIVE)
        if existing_status_changed_at is not None:
            item.setdefault("fact_status_changed_at", existing_status_changed_at)
        if existing_status_reason is not None:
            item.setdefault("fact_status_reason", existing_status_reason)
        if existing_superseded_by is not None:
            item.setdefault("superseded_by_fact_id", existing_superseded_by)
        if existing_lifecycle_history and "fact_lifecycle_history" not in item:
            item["fact_lifecycle_history"] = existing_lifecycle_history

    item["learned_at"] = existing_learned_at or datetime.now(timezone.utc).isoformat()
    rows.append(item)
    entity.db.knowledge_facts = rows
    return {
        "status": "CREATED" if created else "UPDATED",
        "build": KNOWLEDGE_FACT_BUILD,
        "fact_lifecycle_build": FACT_LIFECYCLE_BUILD,
        "fact": dict(item),
        "fact_id": fact_id,
        "created": created,
        "entity_dbref": int(entity.id),
        "entity_name": entity.key,
    }


def set_knowledge_fact_status(entity, fact_id, status, *, reason=None, superseded_by_fact_id=None):
    """Change one holder-local Fact lifecycle state without deleting its Knowledge or provenance."""
    if not entity:
        return {"success": False, "reason": "NO_ENTITY", "build": FACT_LIFECYCLE_BUILD}
    wanted = str(fact_id or "").strip()
    if not wanted:
        return {"success": False, "reason": "BAD_FACT_ID", "build": FACT_LIFECYCLE_BUILD}

    normalized = _normalized_fact_status(status)
    if normalized not in _ALLOWED_FACT_STATUSES:
        return {
            "success": False,
            "reason": "BAD_FACT_STATUS",
            "fact_id": wanted,
            "requested_status": normalized,
            "build": FACT_LIFECYCLE_BUILD,
        }

    replacement_id = str(superseded_by_fact_id or "").strip()
    if normalized == FACT_STATUS_SUPERSEDED and not replacement_id:
        return {
            "success": False,
            "reason": "SUPERSEDED_REQUIRES_REPLACEMENT_FACT_ID",
            "fact_id": wanted,
            "requested_status": normalized,
            "build": FACT_LIFECYCLE_BUILD,
        }
    if replacement_id and replacement_id == wanted:
        return {
            "success": False,
            "reason": "FACT_CANNOT_SUPERSEDE_ITSELF",
            "fact_id": wanted,
            "requested_status": normalized,
            "build": FACT_LIFECYCLE_BUILD,
        }

    rows = []
    found = None
    now = datetime.now(timezone.utc).isoformat()
    for raw in _plain_list(getattr(entity.db, "knowledge_facts", [])):
        item = _record(raw)
        if item is None:
            continue
        if str(item.get("id") or "") != wanted:
            rows.append(item)
            continue

        before = _normalized_fact_status(item.get("fact_status"))
        if before == normalized and (
            normalized != FACT_STATUS_SUPERSEDED
            or str(item.get("superseded_by_fact_id") or "") == replacement_id
        ):
            found = {
                "success": True,
                "changed": False,
                "reason": "NO_CHANGE",
                "fact_id": wanted,
                "before": before,
                "after": normalized,
                "fact": dict(item),
                "build": FACT_LIFECYCLE_BUILD,
            }
            rows.append(item)
            continue

        history = []
        for history_raw in _plain_list(item.get("fact_lifecycle_history")):
            history_row = _record(history_raw)
            if history_row is not None:
                history.append(history_row)
        history.append(
            {
                "from": before,
                "to": normalized,
                "changed_at": now,
                "reason": str(reason or "") or None,
                "superseded_by_fact_id": replacement_id or None,
            }
        )
        item["fact_lifecycle_history"] = history[-FACT_LIFECYCLE_HISTORY_LIMIT:]
        item["fact_status"] = normalized
        item["fact_status_changed_at"] = now
        if reason:
            item["fact_status_reason"] = str(reason)
        else:
            item.pop("fact_status_reason", None)
        if normalized == FACT_STATUS_SUPERSEDED:
            item["superseded_by_fact_id"] = replacement_id
        else:
            item.pop("superseded_by_fact_id", None)

        found = {
            "success": True,
            "changed": True,
            "reason": "FACT_STATUS_CHANGED",
            "fact_id": wanted,
            "before": before,
            "after": normalized,
            "fact": dict(item),
            "build": FACT_LIFECYCLE_BUILD,
        }
        rows.append(item)

    if found is None:
        return {
            "success": False,
            "reason": "FACT_NOT_FOUND",
            "fact_id": wanted,
            "requested_status": normalized,
            "build": FACT_LIFECYCLE_BUILD,
        }

    entity.db.knowledge_facts = rows
    return found


def remove_knowledge_fact(entity, fact_id):
    if not entity:
        return False
    wanted = str(fact_id or "").strip()
    rows = []
    removed = False
    for raw in _plain_list(getattr(entity.db, "knowledge_facts", [])):
        item = _record(raw)
        if item is None:
            continue
        if str(item.get("id") or "") == wanted:
            removed = True
            continue
        rows.append(item)
    entity.db.knowledge_facts = rows
    return removed


def find_knowledge_fact(entity, fact_id):
    wanted = str(fact_id or "").strip()
    return next(
        (dict(row) for row in knowledge_facts(entity) if str(row.get("id") or "") == wanted),
        None,
    )
