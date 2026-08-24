from services.perception_engine import parse_perception_intent, resolve_perception
from services.perception_knowledge_projection_engine import project_discovered_perception_facts


DETERMINISTIC_ACTIVE_PERCEPTION_BUILD = "0.78.0-deterministic-active-perception-knowledge-projection"


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


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


def execute_deterministic_active_perception(actor, raw):
    """Run an already-recognized deterministic active perception and apply authored Knowledge projection atomically."""
    if not actor:
        return {"status": "NO_ACTOR", "executed": False, "build": DETERMINISTIC_ACTIVE_PERCEPTION_BUILD}

    intent = parse_perception_intent(str(raw or ""))
    if not intent or not bool(intent.get("active_search")):
        return {
            "status": "NOT_ACTIVE_PERCEPTION",
            "executed": False,
            "intent": intent,
            "build": DETERMINISTIC_ACTIVE_PERCEPTION_BUILD,
        }

    room = getattr(actor, "location", None)
    if not room:
        return {"status": "NO_LOCATION", "executed": False, "build": DETERMINISTIC_ACTIVE_PERCEPTION_BUILD}

    before_discovered = _clone(getattr(actor.db, "discovered_facts", []))
    before_knowledge = _clone(getattr(actor.db, "knowledge", {}))
    before_facts = _clone(getattr(actor.db, "knowledge_facts", []))

    result = resolve_perception(actor, intent)
    engine_status = str((result or {}).get("status") or "")
    allowed = {"DISCOVERY", "NO_DISCOVERY", "NO_AUTHORIZED_DISCOVERY", "AUTO_SUCCESS"}
    if engine_status not in allowed:
        actor.db.discovered_facts = before_discovered
        actor.db.knowledge = before_knowledge
        actor.db.knowledge_facts = before_facts
        return {
            "status": "PERCEPTION_ENGINE_REJECTED",
            "executed": False,
            "engine_status": engine_status,
            "result": result,
            "restored": True,
            "build": DETERMINISTIC_ACTIVE_PERCEPTION_BUILD,
        }

    after_discovered = _plain_list(getattr(actor.db, "discovered_facts", []))
    before_ids = {str(item) for item in _plain_list(before_discovered)}
    added_ids = [item for item in after_discovered if str(item) not in before_ids]
    projection = project_discovered_perception_facts(actor, room, added_ids)

    if not bool(projection.get("success")):
        actor.db.discovered_facts = before_discovered
        actor.db.knowledge = before_knowledge
        actor.db.knowledge_facts = before_facts
        return {
            "status": "PROJECTION_FAILED",
            "executed": False,
            "engine_status": engine_status,
            "result": result,
            "knowledge_projection": projection,
            "restored": True,
            "build": DETERMINISTIC_ACTIVE_PERCEPTION_BUILD,
        }

    return {
        "status": "DETERMINISTIC_ACTIVE_PERCEPTION_EXECUTED",
        "executed": True,
        "engine_status": engine_status,
        "intent": intent,
        "result": result,
        "discovered_fact_ids_added": list(added_ids),
        "knowledge_projection": projection,
        "build": DETERMINISTIC_ACTIVE_PERCEPTION_BUILD,
    }
