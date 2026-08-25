from services.interaction_engine import (
    _extract_topic,
    _fact_matches_topic,
    _find_npc,
    _plain_list,
)
from services.interaction_proposal_execution_bridge import extract_player_authored_topic
from services.knowledge_context_engine import fact_knowledge_state
from services.conversation_fact_acquisition_engine import resolve_interaction_with_fact_acquisition


NPC_FACT_DISCLOSURE_BUILD = "0.84.0-authored-min-familiarity-fact-disclosure"
_ALLOWED_DISCLOSURE_KEYS = {"min_familiarity"}


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _visible_local_npc_by_dbref(actor, dbref):
    location = getattr(actor, "location", None) if actor else None
    if not location:
        return None
    try:
        wanted = int(dbref)
    except (TypeError, ValueError):
        return None
    for obj in list(getattr(location, "contents", []) or []):
        if getattr(obj, "id", None) != wanted:
            continue
        if bool(getattr(obj.db, "hidden", False)):
            return None
        if not bool(getattr(obj.db, "is_npc", False)):
            return None
        return obj
    return None


def _relationship_familiarity(npc, actor):
    if not npc or not actor:
        return 0
    try:
        actor_dbref = int(actor.id)
    except (TypeError, ValueError):
        return 0
    relationships = _plain_dict(getattr(npc.db, "relationships", {}))
    best = 0
    for raw in relationships.values():
        row = _plain_dict(raw)
        try:
            target_dbref = int(row.get("target_dbref"))
        except (TypeError, ValueError):
            continue
        if target_dbref != actor_dbref:
            continue
        try:
            best = max(best, int(row.get("familiarity", 0) or 0))
        except (TypeError, ValueError):
            continue
    return max(0, best)


def _first_shareable_topic_fact(npc, topic):
    """Mirror the closed interaction engine's first known matching response candidate without mutating anything."""
    if not npc or not topic:
        return None
    for raw_fact in _plain_list(getattr(npc.db, "knowledge_facts", [])):
        fact = _plain_dict(raw_fact)
        if not fact or not _fact_matches_topic(fact, topic):
            continue
        if not bool(fact_knowledge_state(npc, fact).get("known")):
            continue
        response = str(fact.get("response") or "").strip()
        if not response:
            response = str(fact.get("fact") or "").strip()
        if not response:
            response = str(fact.get("text") or "").strip()
        if response:
            return fact
    return None


def evaluate_fact_disclosure(npc, actor, fact):
    """Evaluate one authored disclosure block. Missing disclosure is public; malformed disclosure fails closed."""
    if not fact or "disclosure" not in fact:
        return {
            "status": "DISCLOSURE_PUBLIC",
            "allowed": True,
            "restricted": False,
            "familiarity": _relationship_familiarity(npc, actor),
            "required_familiarity": 0,
            "build": NPC_FACT_DISCLOSURE_BUILD,
        }

    raw = fact.get("disclosure")
    try:
        disclosure = {str(key): value for key, value in raw.items()}
    except Exception:
        disclosure = None
    familiarity = _relationship_familiarity(npc, actor)
    if disclosure is None or set(disclosure) - _ALLOWED_DISCLOSURE_KEYS or "min_familiarity" not in disclosure:
        return {
            "status": "DISCLOSURE_MALFORMED_BLOCKED",
            "allowed": False,
            "restricted": True,
            "familiarity": familiarity,
            "required_familiarity": None,
            "build": NPC_FACT_DISCLOSURE_BUILD,
        }

    raw_required = disclosure.get("min_familiarity")
    if isinstance(raw_required, bool):
        required = None
    else:
        try:
            required = int(raw_required)
        except (TypeError, ValueError):
            required = None
    if required is None or required < 0:
        return {
            "status": "DISCLOSURE_MALFORMED_BLOCKED",
            "allowed": False,
            "restricted": True,
            "familiarity": familiarity,
            "required_familiarity": None,
            "build": NPC_FACT_DISCLOSURE_BUILD,
        }

    allowed = familiarity >= required
    return {
        "status": "DISCLOSURE_ALLOWED" if allowed else "DISCLOSURE_BLOCKED",
        "allowed": bool(allowed),
        "restricted": bool(required > 0),
        "familiarity": familiarity,
        "required_familiarity": required,
        "build": NPC_FACT_DISCLOSURE_BUILD,
    }


def preflight_talk_disclosure(actor, raw, *, expected_target_dbref=None):
    """Check the exact Fact the closed TALK engine would share first, without exposing its private content."""
    location = getattr(actor, "location", None) if actor else None
    if not actor or not location:
        return {
            "status": "DISCLOSURE_NOT_APPLICABLE",
            "allowed": True,
            "applicable": False,
            "build": NPC_FACT_DISCLOSURE_BUILD,
        }

    npc = (
        _visible_local_npc_by_dbref(actor, expected_target_dbref)
        if expected_target_dbref is not None
        else _find_npc(location, raw)
    )
    if not npc:
        return {
            "status": "DISCLOSURE_TARGET_UNRESOLVED",
            "allowed": True,
            "applicable": False,
            "build": NPC_FACT_DISCLOSURE_BUILD,
        }

    topic = str(extract_player_authored_topic(raw) or _extract_topic(raw, npc=npc) or "").strip()
    if not topic:
        return {
            "status": "DISCLOSURE_NO_TOPIC",
            "allowed": True,
            "applicable": False,
            "target_dbref": int(npc.id),
            "target_name": str(npc.key),
            "build": NPC_FACT_DISCLOSURE_BUILD,
        }

    fact = _first_shareable_topic_fact(npc, topic)
    if not fact:
        return {
            "status": "DISCLOSURE_NO_MATCHING_KNOWN_FACT",
            "allowed": True,
            "applicable": False,
            "target_dbref": int(npc.id),
            "target_name": str(npc.key),
            "topic": topic,
            "build": NPC_FACT_DISCLOSURE_BUILD,
        }

    gate = evaluate_fact_disclosure(npc, actor, fact)
    if bool(gate.get("allowed")):
        return {
            **gate,
            "applicable": True,
            "target_dbref": int(npc.id),
            "target_name": str(npc.key),
            "topic": topic,
        }

    return {
        **gate,
        "applicable": True,
        "target_dbref": int(npc.id),
        "target_name": str(npc.key),
        "topic": topic,
        "response_text": f"{npc.key} evita dar detalles sobre {topic}.",
    }


def resolve_interaction_with_disclosure_and_acquisition(actor, intent, *, expected_target_dbref=None):
    """Block a restricted Fact before the closed interaction/acquisition engine can render or transfer it."""
    payload = dict(intent or {})
    if str(payload.get("intent") or "") != "TALK":
        return resolve_interaction_with_fact_acquisition(actor, payload)

    preflight = preflight_talk_disclosure(
        actor,
        payload.get("raw") or "",
        expected_target_dbref=expected_target_dbref,
    )
    if not bool(preflight.get("allowed", True)):
        return {
            "status": "INTERACTION_EXECUTED",
            "executed": True,
            "response_text": str(preflight.get("response_text") or "").strip(),
            "knowledge_acquisition": {
                "status": "DISCLOSURE_BLOCKED",
                "acquired": False,
                "build": NPC_FACT_DISCLOSURE_BUILD,
            },
            "disclosure": preflight,
            "build": NPC_FACT_DISCLOSURE_BUILD,
        }

    base = resolve_interaction_with_fact_acquisition(actor, payload)
    return {**dict(base or {}), "disclosure": preflight}
