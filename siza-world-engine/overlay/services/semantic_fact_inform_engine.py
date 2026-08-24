from services.action_intent_proposal_engine import build_local_capability_catalog
from services.action_proposal_execution_bridge import MIN_EXECUTION_CONFIDENCE
from services.interaction_engine import normalize
from services.interaction_proposal_execution_bridge import extract_player_authored_topic
from services.knowledge_fact_retrieval_engine import retrieve_known_facts
from services.knowledge_fact_transfer_engine import transfer_knowledge_fact


SEMANTIC_FACT_INFORM_BUILD = "0.79.0-player-known-fact-inform"
INFORM_WORDS = {
    "cuento", "contar", "comparto", "compartir", "informo", "informar",
    "comunico", "comunicar", "relato", "relatar",
}
MAX_RETRIEVAL_FACTS = 3


def _proposal_dict(proposal_result):
    try:
        return {str(key): value for key, value in (proposal_result.get("proposal") or {}).items()}
    except Exception:
        return {}


def parse_semantic_fact_inform_intent(raw):
    """Recognize a narrow player-authored fact-sharing intent without deriving factual content from the model."""
    text = normalize(raw)
    tokens = set(text.split())
    if not (tokens & INFORM_WORDS):
        return None
    topic = extract_player_authored_topic(raw)
    if not topic:
        return None
    return {
        "intent": "INFORM_FACT",
        "topic": topic,
        "topic_source": "PLAYER_INPUT",
        "raw": str(raw or ""),
    }


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


def execute_validated_fact_inform_proposal(
    actor,
    proposal_result,
    *,
    raw_player_input="",
    min_confidence=MIN_EXECUTION_CONFIDENCE,
):
    """Let qwen select only a current TALK target; choose and transfer only a Fact the player already knows."""
    if not actor:
        return {"status": "NO_ACTOR", "executed": False, "build": SEMANTIC_FACT_INFORM_BUILD}
    if not isinstance(proposal_result, dict):
        return {"status": "INVALID_PROPOSAL_RESULT", "executed": False, "build": SEMANTIC_FACT_INFORM_BUILD}

    intent = parse_semantic_fact_inform_intent(raw_player_input)
    if not intent:
        return {"status": "NOT_FACT_INFORM_INTENT", "executed": False, "build": SEMANTIC_FACT_INFORM_BUILD}

    if proposal_result.get("status") != "ACCEPTED" or proposal_result.get("accepted") is not True:
        return {
            "status": "PROPOSAL_NOT_ACCEPTED",
            "executed": False,
            "proposal_status": proposal_result.get("status"),
            "build": SEMANTIC_FACT_INFORM_BUILD,
        }

    proposal = _proposal_dict(proposal_result)
    if str(proposal.get("kind") or "") != "INTERACTION":
        return {
            "status": "UNSUPPORTED_EXECUTION_KIND",
            "executed": False,
            "kind": proposal.get("kind"),
            "build": SEMANTIC_FACT_INFORM_BUILD,
        }

    try:
        confidence = float(proposal.get("confidence"))
        threshold = float(min_confidence)
    except (TypeError, ValueError):
        return {"status": "INVALID_CONFIDENCE", "executed": False, "build": SEMANTIC_FACT_INFORM_BUILD}
    if confidence < threshold:
        return {
            "status": "LOW_CONFIDENCE",
            "executed": False,
            "confidence": confidence,
            "required_confidence": threshold,
            "build": SEMANTIC_FACT_INFORM_BUILD,
        }

    capability_id = str(proposal.get("capability_id") or "").strip()
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
            "build": SEMANTIC_FACT_INFORM_BUILD,
        }
    if str(current.get("kind") or "") != "INTERACTION":
        return {
            "status": "CURRENT_KIND_MISMATCH",
            "executed": False,
            "capability_id": capability_id,
            "current_kind": current.get("kind"),
            "build": SEMANTIC_FACT_INFORM_BUILD,
        }

    npc = _find_local_visible_npc(actor, current.get("target_dbref"))
    if not npc:
        return {
            "status": "CURRENT_TARGET_NOT_LOCAL",
            "executed": False,
            "capability_id": capability_id,
            "target_dbref": current.get("target_dbref"),
            "build": SEMANTIC_FACT_INFORM_BUILD,
        }

    topic = str(intent.get("topic") or "").strip()
    retrieval = retrieve_known_facts(
        actor,
        query=topic,
        site=getattr(actor, "location", None),
        max_facts=MAX_RETRIEVAL_FACTS,
    )
    selected = list(retrieval.get("selected") or [])
    if not selected:
        return {
            "status": "NO_KNOWN_FACT_FOR_TOPIC",
            "executed": False,
            "target_dbref": int(npc.id),
            "target_name": str(npc.key),
            "topic": topic,
            "topic_source": "PLAYER_INPUT",
            "retrieval": retrieval,
            "build": SEMANTIC_FACT_INFORM_BUILD,
        }
    if len(selected) != 1:
        return {
            "status": "AMBIGUOUS_KNOWN_FACT_FOR_TOPIC",
            "executed": False,
            "target_dbref": int(npc.id),
            "target_name": str(npc.key),
            "topic": topic,
            "topic_source": "PLAYER_INPUT",
            "candidate_fact_ids": [row.get("id") for row in selected],
            "retrieval": retrieval,
            "build": SEMANTIC_FACT_INFORM_BUILD,
        }

    fact = dict(selected[0])
    fact_id = str(fact.get("id") or "").strip()
    transfer = transfer_knowledge_fact(actor, npc, fact_id)
    if not bool(transfer.get("success")):
        return {
            "status": "FACT_TRANSFER_REJECTED",
            "executed": False,
            "target_dbref": int(npc.id),
            "target_name": str(npc.key),
            "topic": topic,
            "fact_id": fact_id,
            "transfer": transfer,
            "build": SEMANTIC_FACT_INFORM_BUILD,
        }

    reason = str(transfer.get("reason") or "")
    if reason == "ALREADY_TRANSFERRED":
        response_text = f"{npc.key} ya había recibido de ti ese hecho sobre {topic}."
    else:
        response_text = f"Le cuentas a {npc.key} lo que sabes sobre {topic}."

    return {
        "status": "FACT_INFORM_EXECUTED",
        "executed": True,
        "capability_id": capability_id,
        "confidence": confidence,
        "required_confidence": threshold,
        "current_capability": dict(current),
        "target_dbref": int(npc.id),
        "target_name": str(npc.key),
        "topic": topic,
        "topic_source": "PLAYER_INPUT",
        "fact_id": fact_id,
        "fact_topic": fact.get("topic"),
        "retrieval_score": fact.get("relevance_score"),
        "transfer": transfer,
        "response_text": response_text,
        "build": SEMANTIC_FACT_INFORM_BUILD,
    }
