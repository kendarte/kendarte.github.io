from datetime import datetime, timezone

from services.consequence_engine import emit_world_action
from services.knowledge_context_engine import fact_knowledge_state, knowledge_levels, set_knowledge_level
from services.knowledge_fact_engine import find_knowledge_fact, upsert_knowledge_fact


FACT_TRANSFER_BUILD = "0.58.0-persistent-fact-transfer"
TRANSFER_HISTORY_LIMIT = 25


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


def _record(value):
    try:
        return {str(key): item for key, item in value.items()}
    except Exception:
        return None


def _entity_token(entity):
    npc_id = str(getattr(entity.db, "npc_id", "") or "").strip() if entity else ""
    if npc_id:
        return f"NPC:{npc_id}"
    return f"DBREF:{int(entity.id)}" if entity else "NONE"


def _transfer_id(source, target, fact_id):
    return f"FACT_TRANSFER:{fact_id}:{_entity_token(source)}:{_entity_token(target)}"


def _transfer_entry(source, target, fact_id, transfer_id, shared_at):
    return {
        "id": transfer_id,
        "fact_id": str(fact_id or ""),
        "mode": "DIRECT_LOCAL",
        "source_name": source.key if source else None,
        "source_dbref": int(source.id) if source else None,
        "source_npc_id": str(getattr(source.db, "npc_id", "") or "") if source else "",
        "target_name": target.key if target else None,
        "target_dbref": int(target.id) if target else None,
        "target_npc_id": str(getattr(target.db, "npc_id", "") or "") if target else "",
        "shared_at": shared_at,
    }


def transfer_knowledge_fact(source, target, fact_id):
    """Share one known structured Fact locally while preserving its original provenance."""
    if not source:
        return {"success": False, "reason": "NO_SOURCE", "build": FACT_TRANSFER_BUILD}
    if not target:
        return {"success": False, "reason": "NO_TARGET", "build": FACT_TRANSFER_BUILD}
    if source == target:
        return {"success": False, "reason": "SAME_ENTITY", "build": FACT_TRANSFER_BUILD}
    if not getattr(source, "location", None) or source.location != getattr(target, "location", None):
        return {"success": False, "reason": "NOT_COLOCATED", "build": FACT_TRANSFER_BUILD}

    fact = find_knowledge_fact(source, fact_id)
    if not fact:
        return {
            "success": False,
            "reason": "SOURCE_FACT_NOT_FOUND",
            "fact_id": str(fact_id or ""),
            "build": FACT_TRANSFER_BUILD,
        }
    source_state = fact_knowledge_state(source, fact)
    if not bool(source_state.get("known")):
        return {
            "success": False,
            "reason": "SOURCE_DOES_NOT_KNOW_FACT",
            "fact_id": fact.get("id"),
            "build": FACT_TRANSFER_BUILD,
        }

    wanted_fact_id = str(fact.get("id") or "")
    transfer_id = _transfer_id(source, target, wanted_fact_id)
    existing = find_knowledge_fact(target, wanted_fact_id)
    existing_history = _plain_list((existing or {}).get("transfer_history"))
    if any(str((_record(row) or {}).get("id") or "") == transfer_id for row in existing_history):
        return {
            "success": True,
            "created": False,
            "reason": "ALREADY_TRANSFERRED",
            "fact_id": wanted_fact_id,
            "transfer_id": transfer_id,
            "source_name": source.key,
            "target_name": target.key,
            "target_known": bool(fact_knowledge_state(target, existing or fact).get("known")),
            "build": FACT_TRANSFER_BUILD,
        }

    now = datetime.now(timezone.utc).isoformat()
    recipient_fact = dict(fact)
    # Keep the original source and learned_by untouched; transfer is a second provenance layer.
    recipient_fact["source"] = _plain_dict(fact.get("source"))
    recipient_fact["learned_by"] = _plain_dict(fact.get("learned_by"))
    recipient_fact["origin_learned_at"] = fact.get("origin_learned_at") or fact.get("learned_at")

    history = list(existing_history)
    history.append(_transfer_entry(source, target, wanted_fact_id, transfer_id, now))
    recipient_fact["transfer_history"] = history[-TRANSFER_HISTORY_LIMIT:]

    required = int(recipient_fact.get("required_level", 1) or 1)
    knowledge_key = str(recipient_fact.get("knowledge_key") or "").strip()
    before_level = int(knowledge_levels(target).get(knowledge_key, 0) or 0) if knowledge_key else 0
    if knowledge_key:
        set_knowledge_level(target, knowledge_key, max(before_level, required))

    fact_result = upsert_knowledge_fact(target, recipient_fact)
    stored = find_knowledge_fact(target, wanted_fact_id)
    target_state = fact_knowledge_state(target, stored or recipient_fact)

    target_npc_id = str(getattr(target.db, "npc_id", "") or "").strip()
    source_npc_id = str(getattr(source.db, "npc_id", "") or "").strip()
    action_packet = {
        "action_id": f"KNOWLEDGE_FACT_SHARED:{transfer_id}",
        "action_type": "KNOWLEDGE_FACT_SHARED",
        "actor_npc_id": source_npc_id,
        "actor_dbref": int(source.id),
        "actor_name": source.key,
        "target_npc_id": target_npc_id,
        "target_dbref": int(target.id),
        "target_name": target.key,
        "fact_id": wanted_fact_id,
        "knowledge_key": knowledge_key,
        "transfer_id": transfer_id,
        "transfer_mode": "DIRECT_LOCAL",
        "site_dbref": int(source.location.id),
        "site_room_id": str(getattr(source.location.db, "room_id", "") or ""),
        "site_name": source.location.key,
        "recipient_ids": [target_npc_id] if target_npc_id else [],
    }
    consequence = emit_world_action(action_packet)

    return {
        "success": True,
        "created": bool(fact_result.get("created")),
        "reason": "FACT_TRANSFERRED",
        "fact_id": wanted_fact_id,
        "transfer_id": transfer_id,
        "source_name": source.key,
        "source_dbref": int(source.id),
        "target_name": target.key,
        "target_dbref": int(target.id),
        "target_npc_id": target_npc_id,
        "knowledge_key": knowledge_key,
        "knowledge_before": before_level,
        "knowledge_after": target_state.get("level"),
        "target_known": bool(target_state.get("known")),
        "transfer_history_count": len(_plain_list((stored or {}).get("transfer_history"))),
        "fact": stored,
        "action_consequence": consequence,
        "build": FACT_TRANSFER_BUILD,
    }
