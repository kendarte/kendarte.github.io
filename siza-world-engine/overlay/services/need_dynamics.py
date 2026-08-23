

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
    """Advance persistent NPC need values by one NPC simulation clock tick.

    The NPC owns its own persistent dynamics clock. Authored dynamics specify
    cadence and bounds; this function does not invent missing rules.
    """
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


def inspect_need_dynamics(npc):
    if not npc:
        return {}
    try:
        clock = int(npc.db.need_dynamics_clock or 0)
    except (TypeError, ValueError):
        clock = 0
    return {
        "clock": clock,
        "rules": [
            item
            for item in (_record(raw) for raw in _plain_list(npc.db.need_dynamics))
            if item is not None
        ],
    }
