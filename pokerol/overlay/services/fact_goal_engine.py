from datetime import datetime, timezone

from services.knowledge_context_engine import FACT_LIFECYCLE_BUILD, fact_knowledge_state, knowledge_facts


FACT_GOAL_BUILD = "0.59.0-fact-driven-npc-goals"
FACT_GOAL_LIFECYCLE_BUILD = "1.01.0-lifecycle-aware-fact-goals"
LIFECYCLE_CANCELLATION_REASON = "SOURCE_FACT_NO_LONGER_ACTIVE"


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


def fact_goal_rules(npc):
    if not npc:
        return []
    output = []
    for raw in _plain_list(getattr(npc.db, "fact_goal_rules", [])):
        item = _record(raw)
        if item is not None and item.get("id"):
            output.append(item)
    return output


def upsert_fact_goal_rule(npc, rule):
    if not npc:
        return {"status": "NO_NPC", "build": FACT_GOAL_BUILD}
    item = _record(rule)
    rule_id = str((item or {}).get("id") or "").strip()
    if not rule_id:
        return {"status": "BAD_RULE", "build": FACT_GOAL_BUILD}
    rows = []
    replaced = False
    for current in fact_goal_rules(npc):
        if str(current.get("id") or "") == rule_id:
            rows.append(dict(item))
            replaced = True
        else:
            rows.append(current)
    if not replaced:
        rows.append(dict(item))
    npc.db.fact_goal_rules = rows
    return {
        "status": "UPDATED" if replaced else "CREATED",
        "build": FACT_GOAL_BUILD,
        "fact_goal_lifecycle_build": FACT_GOAL_LIFECYCLE_BUILD,
        "rule_id": rule_id,
    }


def _known_fact_ids(npc):
    return {
        str(fact.get("id") or "")
        for fact in knowledge_facts(npc)
        if fact.get("id") and fact_knowledge_state(npc, fact).get("known") is True
    }


def _decision_goals(npc):
    output = []
    for raw in _plain_list(getattr(npc.db, "decision_goals", [])):
        item = _record(raw)
        if item is not None and item.get("id"):
            output.append(item)
    return output


def _refresh_existing_fact_goal_lifecycle(goals, known_fact_ids):
    cancelled = []
    reactivated = []
    changed = False
    now = datetime.now(timezone.utc).isoformat()

    for goal in goals:
        source_fact_id = str(goal.get("source_fact_id") or "").strip()
        if not source_fact_id:
            continue
        goal_id = str(goal.get("id") or "").strip()
        active = bool(goal.get("active", False))
        status = str(goal.get("status") or "").strip().lower()
        cancellation_reason = str(goal.get("cancellation_reason") or "").strip()

        if active and source_fact_id not in known_fact_ids:
            goal["active"] = False
            goal["status"] = "cancelled"
            goal["cancelled_at"] = now
            goal["cancellation_reason"] = LIFECYCLE_CANCELLATION_REASON
            cancelled.append(goal_id)
            changed = True
            continue

        if (
            not active
            and status == "cancelled"
            and cancellation_reason == LIFECYCLE_CANCELLATION_REASON
            and source_fact_id in known_fact_ids
        ):
            goal["active"] = True
            goal["status"] = "pending"
            goal.pop("cancelled_at", None)
            goal.pop("cancellation_reason", None)
            reactivated.append(goal_id)
            changed = True

    return changed, cancelled, reactivated


def refresh_fact_driven_goals(npc):
    """Materialize and lifecycle-gate Fact-authored goals while preserving one-shot completion."""
    if not npc:
        return {
            "status": "NO_NPC",
            "build": FACT_GOAL_BUILD,
            "fact_lifecycle_build": FACT_LIFECYCLE_BUILD,
            "fact_goal_lifecycle_build": FACT_GOAL_LIFECYCLE_BUILD,
            "materialized": [],
            "cancelled": [],
            "reactivated": [],
        }

    known = _known_fact_ids(npc)
    goals = _decision_goals(npc)
    lifecycle_changed, cancelled, reactivated = _refresh_existing_fact_goal_lifecycle(goals, known)
    existing_ids = {str(goal.get("id") or "") for goal in goals}
    materialized = []

    for rule in fact_goal_rules(npc):
        if not bool(rule.get("enabled", False)):
            continue
        fact_id = str(rule.get("fact_id") or "").strip()
        goal = _record(rule.get("goal"))
        goal_id = str((goal or {}).get("id") or "").strip()
        if not fact_id or not goal_id or fact_id not in known:
            continue

        # Existing goals are never recreated here. Lifecycle-only cancellations
        # are reactivated above; completed/other terminal goals stay one-shot.
        if goal_id in existing_ids:
            continue

        goal["id"] = goal_id
        goal["active"] = True
        goal["fact_goal_rule_id"] = str(rule.get("id") or "")
        goal["source_fact_id"] = fact_id
        goal.setdefault("canon_status", "prototype")
        goals.append(goal)
        existing_ids.add(goal_id)
        materialized.append(goal_id)

    if materialized or lifecycle_changed:
        npc.db.decision_goals = goals

    return {
        "status": "MATERIALIZED" if materialized else "NO_CHANGE",
        "build": FACT_GOAL_BUILD,
        "fact_lifecycle_build": FACT_LIFECYCLE_BUILD,
        "fact_goal_lifecycle_build": FACT_GOAL_LIFECYCLE_BUILD,
        "known_fact_ids": sorted(known),
        "materialized": materialized,
        "cancelled": cancelled,
        "reactivated": reactivated,
    }


def remove_fact_goal(npc, goal_id):
    if not npc:
        return False
    wanted = str(goal_id or "").strip()
    goals = _decision_goals(npc)
    kept = [goal for goal in goals if str(goal.get("id") or "") != wanted]
    removed = len(kept) != len(goals)
    if removed:
        npc.db.decision_goals = kept
    return removed


def find_decision_goal(npc, goal_id):
    wanted = str(goal_id or "").strip()
    return next((goal for goal in _decision_goals(npc) if str(goal.get("id") or "") == wanted), None)
