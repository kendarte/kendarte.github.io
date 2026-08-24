from services.knowledge_context_engine import fact_knowledge_state, knowledge_facts


FACT_GOAL_BUILD = "0.59.0-fact-driven-npc-goals"


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


def refresh_fact_driven_goals(npc):
    """Materialize a fact-authored goal once when its required Fact is actually known."""
    if not npc:
        return {"status": "NO_NPC", "build": FACT_GOAL_BUILD, "materialized": []}

    known = _known_fact_ids(npc)
    goals = _decision_goals(npc)
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

        # Existing goals are never reactivated here. This preserves one-shot completion.
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

    if materialized:
        npc.db.decision_goals = goals

    return {
        "status": "MATERIALIZED" if materialized else "NO_CHANGE",
        "build": FACT_GOAL_BUILD,
        "known_fact_ids": sorted(known),
        "materialized": materialized,
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
