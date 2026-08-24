from datetime import datetime, timezone

from services.knowledge_context_engine import knowledge_facts


KNOWLEDGE_FACT_BUILD = "0.57.0-persistent-knowledge-facts"


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


def upsert_knowledge_fact(entity, fact, action=None):
    """Persist one structured Knowledge Fact on any Character/NPC, idempotent by fact id."""
    if not entity:
        return {"status": "NO_ENTITY", "build": KNOWLEDGE_FACT_BUILD}

    item = _record(fact)
    fact_id = str((item or {}).get("id") or "").strip()
    if not fact_id:
        return {"status": "BAD_FACT", "build": KNOWLEDGE_FACT_BUILD}

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
    for raw in _plain_list(getattr(entity.db, "knowledge_facts", [])):
        current = _record(raw)
        if current is None:
            continue
        if str(current.get("id") or "") != fact_id:
            rows.append(current)
            continue
        created = False
        existing_learned_at = current.get("learned_at")

    item["learned_at"] = existing_learned_at or datetime.now(timezone.utc).isoformat()
    rows.append(item)
    entity.db.knowledge_facts = rows
    return {
        "status": "CREATED" if created else "UPDATED",
        "build": KNOWLEDGE_FACT_BUILD,
        "fact": dict(item),
        "fact_id": fact_id,
        "created": created,
        "entity_dbref": int(entity.id),
        "entity_name": entity.key,
    }


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
