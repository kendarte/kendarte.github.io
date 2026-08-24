from evennia import search_object, search_tag

from services.knowledge_fact_transfer_engine import transfer_knowledge_fact
from services.object_action_engine import begin_object_action


FACT_GOAL_COMPLETION_BUILD = "0.60.0-fact-goal-completion-effects"
FACT_GOAL_OBJECT_ACTION_BUILD = "0.62.0-goal-completion-object-action"
ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
LEDGER_ATTR = "fact_goal_completion_action_ids"
LEDGER_LIMIT = 100


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


def completion_rules(npc):
    if not npc:
        return []
    output = []
    for raw in _plain_list(getattr(npc.db, "fact_goal_completion_rules", [])):
        item = _record(raw)
        if item is not None and item.get("id"):
            output.append(item)
    return output


def upsert_completion_rule(npc, rule):
    if not npc:
        return {"status": "NO_NPC", "build": FACT_GOAL_COMPLETION_BUILD}
    item = _record(rule)
    rule_id = str((item or {}).get("id") or "").strip()
    if not rule_id:
        return {"status": "BAD_RULE", "build": FACT_GOAL_COMPLETION_BUILD}

    rows = []
    replaced = False
    for current in completion_rules(npc):
        if str(current.get("id") or "") == rule_id:
            rows.append(dict(item))
            replaced = True
        else:
            rows.append(current)
    if not replaced:
        rows.append(dict(item))
    npc.db.fact_goal_completion_rules = rows
    return {
        "status": "UPDATED" if replaced else "CREATED",
        "build": FACT_GOAL_COMPLETION_BUILD,
        "rule_id": rule_id,
    }


def _find_npc_by_id(npc_id):
    wanted = str(npc_id or "").strip()
    if not wanted:
        return None
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(getattr(obj.db, "npc_id", "") or "").strip() == wanted:
            return obj
    return None


def _find_object_by_identity(object_name, object_id):
    name = str(object_name or "").strip()
    wanted_id = str(object_id or "").strip()
    if not name or not wanted_id:
        return None
    for obj in search_object(name):
        if str(getattr(obj.db, "object_id", "") or "").strip() == wanted_id:
            return obj
    return None


def _ledger(npc):
    return [str(value) for value in _plain_list(getattr(npc.db, LEDGER_ATTR, [])) if value]


def _store_ledger(npc, action_id):
    rows = _ledger(npc)
    if action_id not in rows:
        rows.append(action_id)
    setattr(npc.db, LEDGER_ATTR, rows[-LEDGER_LIMIT:])


def clear_completion_ledger(npc, prefix=None):
    if not npc:
        return 0
    rows = _ledger(npc)
    if prefix is None:
        removed = len(rows)
        setattr(npc.db, LEDGER_ATTR, [])
        return removed
    wanted = str(prefix)
    kept = [row for row in rows if not row.startswith(wanted)]
    setattr(npc.db, LEDGER_ATTR, kept)
    return len(rows) - len(kept)


def _apply_share_fact_effect(npc, rule, rule_id, action_id):
    target = _find_npc_by_id(rule.get("target_npc_id"))
    fact_id = str(rule.get("fact_id") or "").strip()
    if not target:
        return {
            "rule_id": rule_id,
            "effect_type": "SHARE_FACT",
            "status": "TARGET_NOT_FOUND",
            "action_id": action_id,
        }, False

    transfer = transfer_knowledge_fact(npc, target, fact_id)
    success = bool(transfer.get("success"))
    return {
        "rule_id": rule_id,
        "effect_type": "SHARE_FACT",
        "status": "APPLIED" if success else "BLOCKED",
        "action_id": action_id,
        "fact_id": fact_id,
        "target_npc_id": str(getattr(target.db, "npc_id", "") or ""),
        "target_name": target.key,
        "transfer": transfer,
    }, success


def _apply_object_action_effect(npc, rule, rule_id, action_id):
    object_id = str(rule.get("object_id") or "").strip()
    object_name = str(rule.get("object_name") or "").strip()
    object_action_id = str(rule.get("object_action_id") or "").strip()
    target = _find_object_by_identity(object_name, object_id)
    if not target:
        return {
            "rule_id": rule_id,
            "effect_type": "OBJECT_ACTION",
            "status": "OBJECT_NOT_FOUND",
            "action_id": action_id,
            "object_id": object_id,
            "object_name": object_name,
            "object_action_id": object_action_id,
            "object_action_build": FACT_GOAL_OBJECT_ACTION_BUILD,
        }, False
    if not object_action_id:
        return {
            "rule_id": rule_id,
            "effect_type": "OBJECT_ACTION",
            "status": "BAD_OBJECT_ACTION_ID",
            "action_id": action_id,
            "object_id": object_id,
            "object_name": object_name,
            "object_action_build": FACT_GOAL_OBJECT_ACTION_BUILD,
        }, False

    object_action = begin_object_action(npc, target, object_action_id)
    status = str(object_action.get("status") or "")
    success = status == "COMPLETED"
    return {
        "rule_id": rule_id,
        "effect_type": "OBJECT_ACTION",
        "status": "APPLIED" if success else "BLOCKED",
        "action_id": action_id,
        "object_id": object_id,
        "object_name": object_name,
        "object_action_id": object_action_id,
        "object_action": object_action,
        "object_action_build": FACT_GOAL_OBJECT_ACTION_BUILD,
    }, success


def apply_goal_completion_effects(npc, decision_packet):
    """Apply authored effects only after a goal actually returns GOAL_COMPLETED."""
    packet = dict(decision_packet or {})
    if not npc or str(packet.get("status") or "") != "GOAL_COMPLETED":
        return {
            "status": "NOT_COMPLETED",
            "build": FACT_GOAL_COMPLETION_BUILD,
            "results": [],
        }

    goal_id = str(packet.get("goal_id") or "").strip()
    if not goal_id:
        return {
            "status": "NO_GOAL_ID",
            "build": FACT_GOAL_COMPLETION_BUILD,
            "results": [],
        }

    results = []
    applied_any = False
    for rule in completion_rules(npc):
        if not bool(rule.get("enabled", False)):
            continue
        if str(rule.get("goal_id") or "") != goal_id:
            continue

        rule_id = str(rule.get("id") or "")
        action_id = f"FACT_GOAL_COMPLETION:{goal_id}:{rule_id}"
        effect_type = str(rule.get("effect_type") or "").upper()
        if action_id in _ledger(npc):
            results.append(
                {
                    "rule_id": rule_id,
                    "effect_type": effect_type,
                    "status": "ALREADY_APPLIED",
                    "action_id": action_id,
                }
            )
            continue

        if effect_type == "SHARE_FACT":
            result, success = _apply_share_fact_effect(npc, rule, rule_id, action_id)
        elif effect_type == "OBJECT_ACTION":
            result, success = _apply_object_action_effect(npc, rule, rule_id, action_id)
        else:
            result = {
                "rule_id": rule_id,
                "effect_type": effect_type,
                "status": "UNSUPPORTED_EFFECT",
                "action_id": action_id,
            }
            success = False

        if success:
            _store_ledger(npc, action_id)
            applied_any = True
        results.append(result)

    return {
        "status": "APPLIED" if applied_any else ("MATCHED_NO_CHANGE" if results else "NO_RULE"),
        "build": FACT_GOAL_COMPLETION_BUILD,
        "goal_id": goal_id,
        "results": results,
    }
