from services.interaction_engine import resolve_interaction
from services.knowledge_context_engine import fact_knowledge_state
from services.knowledge_fact_engine import find_knowledge_fact
from services.knowledge_fact_transfer_engine import transfer_knowledge_fact


CONVERSATION_FACT_ACQUISITION_BUILD = "0.80.0-authoritative-npc-to-player-fact-acquisition"


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


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


def _new_shared_fact_memory(actor, before_memory_count):
    memories = _plain_list(getattr(actor.db, "memories", []))
    try:
        start = max(0, int(before_memory_count))
    except (TypeError, ValueError):
        start = len(memories)
    for raw in reversed(memories[start:]):
        row = _plain_dict(raw)
        if str(row.get("type") or "") != "conversation":
            continue
        if int(row.get("schema", 1) or 1) < 2:
            continue
        if str(row.get("outcome") or "") != "knowledge_shared":
            continue
        if not str(row.get("fact_id") or "").strip():
            continue
        return row
    return None


def acquire_fact_from_new_conversation(actor, before_memory_count, expected_target_dbref=None):
    """Persist only the exact Fact the existing interaction engine just recorded as shared by a local NPC."""
    if not actor:
        return {"status": "NO_ACTOR", "acquired": False, "build": CONVERSATION_FACT_ACQUISITION_BUILD}

    memory = _new_shared_fact_memory(actor, before_memory_count)
    if not memory:
        return {
            "status": "NO_SHARED_FACT_IN_NEW_CONVERSATION",
            "acquired": False,
            "build": CONVERSATION_FACT_ACQUISITION_BUILD,
        }

    target_dbref = memory.get("with_id")
    if expected_target_dbref is not None:
        try:
            if int(target_dbref) != int(expected_target_dbref):
                return {
                    "status": "CONVERSATION_TARGET_MISMATCH",
                    "acquired": False,
                    "memory_target_dbref": target_dbref,
                    "expected_target_dbref": expected_target_dbref,
                    "build": CONVERSATION_FACT_ACQUISITION_BUILD,
                }
        except (TypeError, ValueError):
            return {
                "status": "INVALID_CONVERSATION_TARGET",
                "acquired": False,
                "build": CONVERSATION_FACT_ACQUISITION_BUILD,
            }

    npc = _visible_local_npc_by_dbref(actor, target_dbref)
    if not npc:
        return {
            "status": "SOURCE_NPC_NOT_CURRENTLY_VISIBLE_LOCAL",
            "acquired": False,
            "target_dbref": target_dbref,
            "build": CONVERSATION_FACT_ACQUISITION_BUILD,
        }

    fact_id = str(memory.get("fact_id") or "").strip()
    source_fact = find_knowledge_fact(npc, fact_id)
    if not source_fact:
        return {
            "status": "SOURCE_FACT_NOT_FOUND_AFTER_CONVERSATION",
            "acquired": False,
            "fact_id": fact_id,
            "source_dbref": int(npc.id),
            "source_name": str(npc.key),
            "build": CONVERSATION_FACT_ACQUISITION_BUILD,
        }
    source_state = fact_knowledge_state(npc, source_fact)
    if not bool(source_state.get("known")):
        return {
            "status": "SOURCE_NO_LONGER_KNOWS_FACT",
            "acquired": False,
            "fact_id": fact_id,
            "source_dbref": int(npc.id),
            "source_name": str(npc.key),
            "build": CONVERSATION_FACT_ACQUISITION_BUILD,
        }

    transfer = transfer_knowledge_fact(npc, actor, fact_id)
    if not bool(transfer.get("success")):
        return {
            "status": "FACT_TRANSFER_REJECTED",
            "acquired": False,
            "fact_id": fact_id,
            "source_dbref": int(npc.id),
            "source_name": str(npc.key),
            "transfer": transfer,
            "build": CONVERSATION_FACT_ACQUISITION_BUILD,
        }

    reason = str(transfer.get("reason") or "")
    return {
        "status": "FACT_ALREADY_ACQUIRED" if reason == "ALREADY_TRANSFERRED" else "FACT_ACQUIRED",
        "acquired": True,
        "created": reason != "ALREADY_TRANSFERRED",
        "fact_id": fact_id,
        "fact_text": memory.get("fact_text"),
        "topic": memory.get("topic"),
        "source_dbref": int(npc.id),
        "source_name": str(npc.key),
        "transfer": transfer,
        "build": CONVERSATION_FACT_ACQUISITION_BUILD,
    }


def resolve_interaction_with_fact_acquisition(actor, intent):
    """Run the existing interaction engine, then persist only an exact Fact it actually shared."""
    before_count = len(_plain_list(getattr(actor.db, "memories", []))) if actor else 0
    response_text = str(resolve_interaction(actor, intent) or "").strip()
    acquisition = acquire_fact_from_new_conversation(actor, before_count)
    return {
        "status": "INTERACTION_EXECUTED" if response_text else "INTERACTION_REJECTED",
        "executed": bool(response_text),
        "response_text": response_text,
        "knowledge_acquisition": acquisition,
        "build": CONVERSATION_FACT_ACQUISITION_BUILD,
    }
