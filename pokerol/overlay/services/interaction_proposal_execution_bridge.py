from services.action_intent_proposal_engine import build_local_capability_catalog
from services.action_proposal_execution_bridge import MIN_EXECUTION_CONFIDENCE
from services.conversation_fact_acquisition_engine import acquire_fact_from_new_conversation
from services.interaction_engine import normalize, resolve_interaction


INTERACTION_BRIDGE_BUILD = "0.74.1-dm-interaction-fact-acquisition"
MAX_TOPIC_CHARS = 180
TOPIC_MARKERS = (
    " tema del ",
    " tema de ",
    " asunto del ",
    " asunto de ",
    " acerca del ",
    " acerca de ",
    " sobre ",
)


def _proposal_dict(proposal_result):
    try:
        return {str(key): value for key, value in (proposal_result.get("proposal") or {}).items()}
    except Exception:
        return {}


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def extract_player_authored_topic(raw_player_input):
    """Extract only an explicit topic phrase authored by the player; never derive topic text from the model proposal."""
    text = normalize(raw_player_input)
    if not text:
        return ""
    padded = f" {text} "
    for marker in TOPIC_MARKERS:
        if marker not in padded:
            continue
        tail = padded.split(marker, 1)[1].strip()
        if not tail:
            return ""
        return tail[:MAX_TOPIC_CHARS].strip()
    return ""


def _find_local_visible_npc(actor, dbref):
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


def execute_validated_interaction_proposal(
    actor,
    proposal_result,
    *,
    raw_player_input="",
    min_confidence=MIN_EXECUTION_CONFIDENCE,
):
    """Revalidate one INTERACTION proposal; qwen chooses only target, while optional topic comes solely from original player text."""
    if not actor:
        return {"status": "NO_ACTOR", "executed": False, "build": INTERACTION_BRIDGE_BUILD}
    if not isinstance(proposal_result, dict):
        return {"status": "INVALID_PROPOSAL_RESULT", "executed": False, "build": INTERACTION_BRIDGE_BUILD}
    if proposal_result.get("status") != "ACCEPTED" or proposal_result.get("accepted") is not True:
        return {
            "status": "PROPOSAL_NOT_ACCEPTED",
            "executed": False,
            "proposal_status": proposal_result.get("status"),
            "build": INTERACTION_BRIDGE_BUILD,
        }

    proposal = _proposal_dict(proposal_result)
    if str(proposal.get("kind") or "") != "INTERACTION":
        return {
            "status": "UNSUPPORTED_EXECUTION_KIND",
            "executed": False,
            "kind": proposal.get("kind"),
            "build": INTERACTION_BRIDGE_BUILD,
        }

    try:
        confidence = float(proposal.get("confidence"))
        threshold = float(min_confidence)
    except (TypeError, ValueError):
        return {"status": "INVALID_CONFIDENCE", "executed": False, "build": INTERACTION_BRIDGE_BUILD}
    if confidence < threshold:
        return {
            "status": "LOW_CONFIDENCE",
            "executed": False,
            "confidence": confidence,
            "required_confidence": threshold,
            "build": INTERACTION_BRIDGE_BUILD,
        }

    capability_id = str(proposal.get("capability_id") or "").strip()
    if not capability_id:
        return {"status": "MISSING_CAPABILITY_ID", "executed": False, "build": INTERACTION_BRIDGE_BUILD}

    current_catalog = build_local_capability_catalog(actor)
    current = next(
        (row for row in current_catalog if str(row.get("capability_id") or "") == capability_id),
        None,
    )
    if not current:
        return {
            "status": "STALE_OR_MISSING_CAPABILITY",
            "executed": False,
            "capability_id": capability_id,
            "current_catalog_count": len(current_catalog),
            "build": INTERACTION_BRIDGE_BUILD,
        }
    if str(current.get("kind") or "") != "INTERACTION":
        return {
            "status": "CURRENT_KIND_MISMATCH",
            "executed": False,
            "capability_id": capability_id,
            "current_kind": current.get("kind"),
            "build": INTERACTION_BRIDGE_BUILD,
        }

    npc = _find_local_visible_npc(actor, current.get("target_dbref"))
    if not npc:
        return {
            "status": "CURRENT_TARGET_NOT_LOCAL",
            "executed": False,
            "capability_id": capability_id,
            "target_dbref": current.get("target_dbref"),
            "build": INTERACTION_BRIDGE_BUILD,
        }

    topic = extract_player_authored_topic(raw_player_input)
    canonical_raw = f"hablar con {npc.key}"
    if topic:
        canonical_raw = f"preguntar a {npc.key} sobre {topic}"
    canonical_intent = {
        "intent": "TALK",
        "raw": canonical_raw,
    }
    before_count = len(_plain_list(getattr(actor.db, "memories", [])))
    response_text = str(resolve_interaction(actor, canonical_intent) or "").strip()
    acquisition = acquire_fact_from_new_conversation(
        actor,
        before_count,
        expected_target_dbref=int(npc.id),
    )
    if not response_text:
        return {
            "status": "INTERACTION_REJECTED",
            "executed": False,
            "capability_id": capability_id,
            "target_dbref": int(npc.id),
            "target_name": str(npc.key),
            "topic": topic or None,
            "knowledge_acquisition": acquisition,
            "build": INTERACTION_BRIDGE_BUILD,
        }

    return {
        "status": "INTERACTION_EXECUTED",
        "executed": True,
        "capability_id": capability_id,
        "confidence": confidence,
        "required_confidence": threshold,
        "current_capability": dict(current),
        "target_dbref": int(npc.id),
        "target_name": str(npc.key),
        "response_text": response_text,
        "interaction_intent": "TALK",
        "topic": topic or None,
        "topic_source": "PLAYER_INPUT" if topic else None,
        "knowledge_acquisition": acquisition,
        "build": INTERACTION_BRIDGE_BUILD,
    }
