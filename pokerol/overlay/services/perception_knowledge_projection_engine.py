from services.knowledge_context_engine import fact_knowledge_state, knowledge_levels
from services.knowledge_fact_engine import find_knowledge_fact, upsert_knowledge_fact


PERCEPTION_KNOWLEDGE_PROJECTION_BUILD = "0.77.0-authored-perception-knowledge-projection"
_ALLOWED_KNOWLEDGE_MODES = {"SET", "ADD", "MAX", "MIN"}


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


def _clone(value):
    if hasattr(value, "items"):
        try:
            return {str(key): _clone(item) for key, item in value.items()}
        except Exception:
            pass
    if isinstance(value, (list, tuple, set)):
        return [_clone(item) for item in value]
    if not isinstance(value, (str, bytes)) and hasattr(value, "__iter__"):
        try:
            return [_clone(item) for item in value]
        except Exception:
            pass
    return value


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _perception_fact_map(room):
    output = {}
    if not room:
        return output
    for raw in _plain_list(getattr(room.db, "perception_facts", [])):
        item = _record(raw)
        fact_id = str((item or {}).get("id") or "").strip()
        if fact_id:
            output[fact_id] = item
    return output


def _projection_specs(perception_fact):
    knowledge_fact = _plain_dict((perception_fact or {}).get("knowledge_fact"))
    knowledge = _plain_dict((perception_fact or {}).get("knowledge"))
    if not knowledge_fact and not knowledge:
        return {"status": "NO_PROJECTION"}
    if not knowledge_fact or not knowledge:
        return {"status": "INVALID_PROJECTION", "reason": "BOTH_KNOWLEDGE_BLOCKS_REQUIRED"}

    fact_id = str(knowledge_fact.get("id") or "").strip()
    fact_text = str(knowledge_fact.get("text") or "").strip()
    fact_key = str(knowledge_fact.get("knowledge_key") or "").strip()
    grant_key = str(knowledge.get("knowledge_key") or "").strip()
    mode = str(knowledge.get("mode") or "").strip().upper()
    if not fact_id or not fact_text or not fact_key or not grant_key:
        return {"status": "INVALID_PROJECTION", "reason": "REQUIRED_FIELDS_MISSING"}
    if fact_key != grant_key:
        return {"status": "INVALID_PROJECTION", "reason": "KNOWLEDGE_KEY_MISMATCH"}
    if mode not in _ALLOWED_KNOWLEDGE_MODES:
        return {"status": "INVALID_PROJECTION", "reason": "INVALID_KNOWLEDGE_MODE"}

    required_level = max(0, _safe_int(knowledge_fact.get("required_level"), 1))
    value = _safe_int(knowledge.get("value"), 0)
    return {
        "status": "VALID",
        "knowledge_fact": knowledge_fact,
        "knowledge": {
            **knowledge,
            "knowledge_key": grant_key,
            "mode": mode,
            "value": value,
        },
        "required_level": required_level,
    }


def _apply_knowledge(actor, spec):
    key = str((spec or {}).get("knowledge_key") or "").strip()
    mode = str((spec or {}).get("mode") or "").strip().upper()
    value = _safe_int((spec or {}).get("value"), 0)
    if not key or mode not in _ALLOWED_KNOWLEDGE_MODES:
        return None

    levels = knowledge_levels(actor)
    before = _safe_int(levels.get(key), 0)
    if mode == "ADD":
        after = before + value
    elif mode == "MAX":
        after = max(before, value)
    elif mode == "MIN":
        after = min(before, value)
    else:
        after = value

    if (spec or {}).get("min_level") is not None:
        after = max(after, _safe_int((spec or {}).get("min_level"), after))
    if (spec or {}).get("max_level") is not None:
        after = min(after, _safe_int((spec or {}).get("max_level"), after))
    after = max(0, int(after))
    levels[key] = after
    actor.db.knowledge = levels
    return {
        "knowledge_key": key,
        "mode": mode,
        "value": value,
        "before": before,
        "after": after,
        "changed": before != after,
    }


def project_discovered_perception_facts(actor, room, discovered_fact_ids):
    """Project newly discovered authored perception facts into persistent Knowledge atomically.

    Perception facts without explicit knowledge_fact + knowledge blocks are intentionally left as
    legacy discovered_facts-only discoveries. Malformed explicit projections fail closed and restore
    Knowledge/Knowledge Facts to their pre-projection snapshots.
    """
    if not actor:
        return {"status": "NO_ACTOR", "success": False, "build": PERCEPTION_KNOWLEDGE_PROJECTION_BUILD}
    if not room:
        return {"status": "NO_ROOM", "success": False, "build": PERCEPTION_KNOWLEDGE_PROJECTION_BUILD}

    ordered_ids = []
    seen = set()
    for value in _plain_list(discovered_fact_ids):
        fact_id = str(value or "").strip()
        if fact_id and fact_id not in seen:
            seen.add(fact_id)
            ordered_ids.append(fact_id)
    if not ordered_ids:
        return {
            "status": "NO_DISCOVERIES",
            "success": True,
            "projected": [],
            "skipped": [],
            "build": PERCEPTION_KNOWLEDGE_PROJECTION_BUILD,
        }

    source_map = _perception_fact_map(room)
    before_knowledge = _clone(getattr(actor.db, "knowledge", {}))
    before_facts = _clone(getattr(actor.db, "knowledge_facts", []))
    projected = []
    skipped = []

    try:
        for perception_fact_id in ordered_ids:
            perception_fact = source_map.get(perception_fact_id)
            if not perception_fact:
                raise ValueError(f"PERCEPTION_FACT_NOT_FOUND:{perception_fact_id}")

            specs = _projection_specs(perception_fact)
            if specs.get("status") == "NO_PROJECTION":
                skipped.append({"perception_fact_id": perception_fact_id, "reason": "NO_PROJECTION"})
                continue
            if specs.get("status") != "VALID":
                raise ValueError(f"{specs.get('reason') or 'INVALID_PROJECTION'}:{perception_fact_id}")

            knowledge_fact = dict(specs.get("knowledge_fact") or {})
            knowledge_spec = dict(specs.get("knowledge") or {})
            required_level = int(specs.get("required_level") or 0)

            source = _plain_dict(knowledge_fact.get("source"))
            source.setdefault("perception_fact_id", perception_fact_id)
            source.setdefault("site_room_id", str(getattr(room.db, "room_id", "") or "") or None)
            source.setdefault("site_dbref", int(room.id))
            source.setdefault("site_name", str(room.key))
            knowledge_fact["source"] = source

            learned_by = _plain_dict(knowledge_fact.get("learned_by"))
            learned_by.setdefault("provider", "PERCEPTION_ENGINE")
            learned_by.setdefault("outcome", "DISCOVERY")
            learned_by.setdefault("perception_fact_id", perception_fact_id)
            knowledge_fact["learned_by"] = learned_by

            knowledge_result = _apply_knowledge(actor, knowledge_spec)
            if not knowledge_result:
                raise ValueError(f"KNOWLEDGE_MUTATION_FAILED:{perception_fact_id}")

            fact_packet = upsert_knowledge_fact(actor, knowledge_fact)
            if str(fact_packet.get("status") or "") not in {"CREATED", "UPDATED"}:
                raise ValueError(f"KNOWLEDGE_FACT_UPSERT_FAILED:{perception_fact_id}")

            stored = find_knowledge_fact(actor, fact_packet.get("fact_id"))
            state = fact_knowledge_state(actor, stored or {})
            if not stored or not bool(state.get("known")) or int(state.get("level") or 0) < required_level:
                raise ValueError(f"PROJECTED_FACT_NOT_KNOWN:{perception_fact_id}")

            projected.append(
                {
                    "perception_fact_id": perception_fact_id,
                    "knowledge_fact_id": fact_packet.get("fact_id"),
                    "fact_status": fact_packet.get("status"),
                    "topic": stored.get("topic"),
                    "text": stored.get("text"),
                    "knowledge_key": state.get("knowledge_key"),
                    "knowledge_level": state.get("level"),
                    "required_level": state.get("required_level"),
                    "knowledge_changed": knowledge_result.get("changed"),
                    "source": _plain_dict(stored.get("source")),
                    "learned_by": _plain_dict(stored.get("learned_by")),
                }
            )
    except Exception as exc:
        actor.db.knowledge = before_knowledge
        actor.db.knowledge_facts = before_facts
        return {
            "status": "PROJECTION_FAILED",
            "success": False,
            "error": str(exc),
            "projected": [],
            "skipped": skipped,
            "restored": True,
            "build": PERCEPTION_KNOWLEDGE_PROJECTION_BUILD,
        }

    return {
        "status": "PROJECTED" if projected else "NO_PROJECTION",
        "success": True,
        "projected": projected,
        "skipped": skipped,
        "build": PERCEPTION_KNOWLEDGE_PROJECTION_BUILD,
    }
