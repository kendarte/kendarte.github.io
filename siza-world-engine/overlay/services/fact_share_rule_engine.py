from evennia import search_tag

from services.knowledge_context_engine import fact_knowledge_state
from services.knowledge_fact_engine import find_knowledge_fact
from services.relationship_engine import create_fact_share_obligation


FACT_SHARE_RULE_BUILD = "0.89.0-fact-driven-social-share-rules"
ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"


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


def _npc_by_id(npc_id):
    wanted = str(npc_id or "").strip()
    if not wanted:
        return None
    for npc in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if not bool(getattr(npc.db, "is_npc", False)):
            continue
        if str(getattr(npc.db, "npc_id", "") or "").strip() == wanted:
            return npc
    return None


def _completed_obligation_exists(npc, target_id, obligation_id):
    relationships = _plain_dict(getattr(npc.db, "relationships", {})) if npc else {}
    relation = _plain_dict(relationships.get(str(target_id), {}))
    for raw in _plain_list(relation.get("obligations")):
        item = _record(raw) or {}
        if str(item.get("id") or "") != str(obligation_id):
            continue
        return not bool(item.get("active", False)) and str(item.get("status") or "").lower() == "completed"
    return False


def fact_share_rules(npc):
    if not npc:
        return []
    output = []
    for raw in _plain_list(getattr(npc.db, "fact_share_rules", [])):
        item = _record(raw)
        if item is not None and item.get("id"):
            output.append(item)
    return output


def upsert_fact_share_rule(npc, rule):
    if not npc:
        return {"status": "NO_NPC", "build": FACT_SHARE_RULE_BUILD}
    item = _record(rule)
    rule_id = str((item or {}).get("id") or "").strip()
    if not rule_id:
        return {"status": "BAD_RULE", "build": FACT_SHARE_RULE_BUILD}
    rows = []
    replaced = False
    for current in fact_share_rules(npc):
        if str(current.get("id") or "") == rule_id:
            rows.append(dict(item))
            replaced = True
        else:
            rows.append(current)
    if not replaced:
        rows.append(dict(item))
    npc.db.fact_share_rules = rows
    return {
        "status": "UPDATED" if replaced else "CREATED",
        "rule_id": rule_id,
        "build": FACT_SHARE_RULE_BUILD,
    }


def refresh_fact_share_obligations(npc):
    """Materialize authored SHARE_FACT obligations only from Facts this NPC actually knows."""
    if not npc:
        return {"status": "NO_NPC", "build": FACT_SHARE_RULE_BUILD, "materialized": []}

    materialized = []
    skipped = []
    for rule in fact_share_rules(npc):
        if not bool(rule.get("enabled", False)):
            continue
        rule_id = str(rule.get("id") or "").strip()
        fact_id = str(rule.get("fact_id") or "").strip()
        target_id = str(rule.get("target_npc_id") or "").strip()
        if not rule_id or not fact_id or not target_id:
            skipped.append({"rule_id": rule_id, "reason": "MALFORMED_RULE"})
            continue

        fact = find_knowledge_fact(npc, fact_id)
        if not fact or not bool(fact_knowledge_state(npc, fact).get("known")):
            skipped.append({"rule_id": rule_id, "reason": "SOURCE_DOES_NOT_KNOW_FACT"})
            continue

        target = _npc_by_id(target_id)
        if not target:
            skipped.append({"rule_id": rule_id, "reason": "TARGET_NOT_FOUND"})
            continue

        obligation_id = f"SHARE-FACT-{target_id}-{fact_id}"
        if bool(rule.get("one_shot", True)) and _completed_obligation_exists(npc, target_id, obligation_id):
            skipped.append({"rule_id": rule_id, "reason": "ALREADY_COMPLETED", "obligation_id": obligation_id})
            continue

        packet = create_fact_share_obligation(
            npc,
            target,
            fact_id,
            priority=rule.get("priority", 50),
        )
        if packet.get("success"):
            materialized.append(
                {
                    "rule_id": rule_id,
                    "obligation_id": packet.get("obligation_id"),
                    "fact_id": fact_id,
                    "target_npc_id": target_id,
                    "created": bool(packet.get("created")),
                }
            )
        else:
            skipped.append({"rule_id": rule_id, "reason": packet.get("reason") or "CREATE_FAILED"})

    return {
        "status": "MATERIALIZED" if materialized else "NO_CHANGE",
        "materialized": materialized,
        "skipped": skipped,
        "build": FACT_SHARE_RULE_BUILD,
    }
