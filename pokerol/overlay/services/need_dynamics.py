def _plain_list(value):
    if not value:
        return []
    try:
        return list(value)
    except Exception:
        return []


def _plain_dict(value):
    if not value:
        return {}
    try:
        return dict(value)
    except Exception:
        return {}


def _record(raw):
    try:
        return {str(key): value for key, value in raw.items()}
    except Exception:
        return None


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _preserve_number_type(before, value):
    if isinstance(before, int) and float(value).is_integer():
        return int(value)
    return value


def _apply_delta(before, rule):
    op = str(rule.get("op") or "add").lower()
    amount = _number(rule.get("value"), 0)
    current = _number(before, 0)

    if op == "set":
        result = amount
    elif op == "sub":
        result = current - amount
    else:
        result = current + amount

    minimum = rule.get("min")
    maximum = rule.get("max")
    if minimum is not None:
        result = max(result, _number(minimum, result))
    if maximum is not None:
        result = min(result, _number(maximum, result))

    return _preserve_number_type(before, result)


def advance_need_dynamics(npc):
    """Advance only CLOCK-based need rules by one persistent NPC simulation tick."""
    if not npc:
        return {"npc": None, "clock": None, "changes": []}

    try:
        clock = int(npc.db.need_dynamics_clock or 0) + 1
    except (TypeError, ValueError):
        clock = 1
    npc.db.need_dynamics_clock = clock

    needs = _plain_dict(npc.db.needs)
    changes = []

    for raw in _plain_list(npc.db.need_dynamics):
        rule = _record(raw)
        if not rule or not bool(rule.get("enabled", True)):
            continue

        source = str(rule.get("source") or "clock").upper()
        if source != "CLOCK":
            continue

        field = str(rule.get("field") or "").strip()
        if not field:
            continue

        try:
            every_ticks = max(1, int(rule.get("every_ticks", 1) or 1))
        except (TypeError, ValueError):
            every_ticks = 1

        if clock % every_ticks != 0:
            continue

        before = needs.get(field, 0)
        after = _apply_delta(before, rule)
        if after == before:
            continue

        needs[field] = after
        changes.append(
            {
                "id": rule.get("id"),
                "source": "CLOCK",
                "field": field,
                "op": str(rule.get("op") or "add"),
                "value": rule.get("value"),
                "before": before,
                "after": after,
                "every_ticks": every_ticks,
                "canon_status": str(rule.get("canon_status") or "prototype"),
            }
        )

    if changes:
        npc.db.needs = needs

    return {
        "npc": npc.key,
        "npc_id": npc.db.npc_id,
        "clock": clock,
        "changes": changes,
    }


def apply_activity_need_dynamics(npc, activity_kind):
    """Apply need rules authored for the action the NPC actually executed.

    Counters are persistent per rule, so cadence survives server restarts and does
    not depend on the global World Tick number.
    """
    kind = str(activity_kind or "IDLE").upper()
    if not npc:
        return {"npc": None, "activity_kind": kind, "changes": [], "counters": {}}

    needs = _plain_dict(npc.db.needs)
    counters = _plain_dict(npc.db.need_activity_counters)
    changes = []

    for raw in _plain_list(npc.db.need_dynamics):
        rule = _record(raw)
        if not rule or not bool(rule.get("enabled", True)):
            continue

        source = str(rule.get("source") or "clock").upper()
        if source != "ACTIVITY":
            continue

        rule_kind = str(rule.get("activity_kind") or "").upper()
        if rule_kind != kind:
            continue

        rule_id = str(rule.get("id") or "").strip()
        field = str(rule.get("field") or "").strip()
        if not rule_id or not field:
            continue

        try:
            every_actions = max(1, int(rule.get("every_actions", 1) or 1))
        except (TypeError, ValueError):
            every_actions = 1

        try:
            count = int(counters.get(rule_id, 0) or 0) + 1
        except (TypeError, ValueError):
            count = 1
        counters[rule_id] = count

        if count % every_actions != 0:
            continue

        before = needs.get(field, 0)
        after = _apply_delta(before, rule)
        if after == before:
            continue

        needs[field] = after
        changes.append(
            {
                "id": rule_id,
                "source": "ACTIVITY",
                "activity_kind": kind,
                "field": field,
                "op": str(rule.get("op") or "add"),
                "value": rule.get("value"),
                "before": before,
                "after": after,
                "every_actions": every_actions,
                "action_count": count,
                "canon_status": str(rule.get("canon_status") or "prototype"),
            }
        )

    npc.db.need_activity_counters = counters
    if changes:
        npc.db.needs = needs

    return {
        "npc": npc.key,
        "npc_id": npc.db.npc_id,
        "activity_kind": kind,
        "changes": changes,
        "counters": counters,
    }


def inspect_need_dynamics(npc):
    if not npc:
        return {}
    try:
        clock = int(npc.db.need_dynamics_clock or 0)
    except (TypeError, ValueError):
        clock = 0
    return {
        "clock": clock,
        "activity_counters": _plain_dict(npc.db.need_activity_counters),
        "rules": [
            item
            for item in (_record(raw) for raw in _plain_list(npc.db.need_dynamics))
            if item is not None
        ],
    }
