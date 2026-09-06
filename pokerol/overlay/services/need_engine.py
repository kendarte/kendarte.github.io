from evennia import search_tag


NEED_SITE_TAG = "siza_need_site"
NEED_SITE_CATEGORY = "siza_need"


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


def _compare(left, op, right):
    op = str(op or "gte").lower()
    try:
        if op in {"lt", "lte", "gt", "gte"}:
            left_value = float(left)
            right_value = float(right)
            if op == "lt":
                return left_value < right_value
            if op == "lte":
                return left_value <= right_value
            if op == "gt":
                return left_value > right_value
            return left_value >= right_value
    except (TypeError, ValueError):
        return False

    if op == "eq":
        return left == right
    if op == "ne":
        return left != right
    return False


def need_sites():
    """Persistent world objects/Rooms that explicitly offer need-resolution affordances."""
    return list(search_tag(NEED_SITE_TAG, category=NEED_SITE_CATEGORY))


def _affordances(site):
    output = []
    for raw in _plain_list(site.db.need_affordances):
        item = _record(raw)
        if item is not None:
            output.append(item)
    return output


def collect_need_candidates(npc, default_priority=70):
    """Derive NEED goals from NPC state plus affordances authored into the world."""
    if not npc:
        return []

    need_state = _plain_dict(npc.db.needs)
    rules = _plain_list(npc.db.need_rules)
    candidates = []

    for raw_rule in rules:
        rule = _record(raw_rule)
        if not rule or not bool(rule.get("enabled", True)):
            continue

        rule_id = str(rule.get("id") or "").strip()
        need_key = str(rule.get("need_key") or "").strip()
        affordance_kind = str(rule.get("affordance") or "").strip()
        if not rule_id or not need_key or not affordance_kind:
            continue

        current_value = need_state.get(need_key)
        threshold = rule.get("value")
        operator = str(rule.get("op") or "gte")
        if not _compare(current_value, operator, threshold):
            continue

        try:
            priority = int(rule.get("priority", default_priority))
        except (TypeError, ValueError):
            priority = int(default_priority)

        for site in need_sites():
            for affordance in _affordances(site):
                if not bool(affordance.get("enabled", True)):
                    continue
                if str(affordance.get("kind") or "") != affordance_kind:
                    continue

                allowed_need = str(affordance.get("need_key") or "").strip()
                if allowed_need and allowed_need != need_key:
                    continue

                affordance_id = str(affordance.get("id") or "").strip()
                if not affordance_id:
                    continue

                candidates.append(
                    {
                        "id": f"NEED:{rule_id}:{site.id}:{affordance_id}",
                        "type": "NEED",
                        "priority": priority,
                        "active": True,
                        "target_room_id": getattr(site.db, "room_id", None),
                        "target_room_key": site.key,
                        "activity": str(
                            rule.get("activity")
                            or affordance.get("activity")
                            or f"atendiendo la necesidad {need_key}"
                        ),
                        "one_shot": True,
                        "source": "NPC_NEED",
                        "need_key": need_key,
                        "need_value": current_value,
                        "need_rule_id": rule_id,
                        "need_operator": operator,
                        "need_threshold": threshold,
                        "affordance": affordance_kind,
                        "affordance_id": affordance_id,
                        "need_site_dbid": site.id,
                        "canon_status": str(
                            rule.get("canon_status")
                            or affordance.get("canon_status")
                            or "prototype"
                        ),
                    }
                )

    return candidates


def _apply_effect(current, effect):
    op = str(effect.get("op") or "set").lower()
    value = effect.get("value")

    if op == "set":
        return value

    try:
        current_number = float(current or 0)
        value_number = float(value or 0)
    except (TypeError, ValueError):
        return current

    if op == "add":
        result = current_number + value_number
    elif op == "sub":
        result = current_number - value_number
    elif op == "min":
        result = min(current_number, value_number)
    elif op == "max":
        result = max(current_number, value_number)
    else:
        return current

    if isinstance(current, int) and float(result).is_integer():
        return int(result)
    return result


def _find_affordance(goal):
    site_dbid = goal.get("need_site_dbid")
    affordance_id = str(goal.get("affordance_id") or "")
    for site in need_sites():
        if site_dbid is not None and int(site.id) != int(site_dbid):
            continue
        for affordance in _affordances(site):
            if str(affordance.get("id") or "") == affordance_id:
                return site, affordance
    return None, None


def complete_need_goal(npc, goal):
    """Resolve a NEED by applying only the effects authored on its world affordance."""
    site, affordance = _find_affordance(goal)
    if not site or not affordance:
        return {
            "completed": False,
            "completion_source": "NPC_NEED",
            "completion_site": None,
            "need_effects": [],
        }

    needs = _plain_dict(npc.db.needs)
    applied = []
    for raw_effect in _plain_list(affordance.get("completion_effects", [])):
        effect = _record(raw_effect)
        if not effect:
            continue
        field = str(effect.get("field") or "").strip()
        if not field:
            continue
        before = needs.get(field)
        after = _apply_effect(before, effect)
        needs[field] = after
        applied.append(
            {
                "field": field,
                "op": str(effect.get("op") or "set"),
                "before": before,
                "after": after,
            }
        )

    if applied:
        npc.db.needs = needs

    return {
        "completed": bool(applied),
        "completion_source": "NPC_NEED",
        "completion_site": site.key,
        "need_effects": applied,
    }


def set_need_value(npc, need_key, value):
    needs = _plain_dict(npc.db.needs)
    needs[str(need_key)] = value
    npc.db.needs = needs
    return needs[str(need_key)]


def inspect_needs(npc):
    """Debug packet for persistent need state, authored rules and world affordances."""
    if not npc:
        return {}

    sites = []
    for site in need_sites():
        sites.append(
            {
                "site": site.key,
                "room_id": getattr(site.db, "room_id", None),
                "affordances": _affordances(site),
            }
        )

    return {
        "npc": npc.key,
        "npc_id": npc.db.npc_id,
        "needs": _plain_dict(npc.db.needs),
        "rules": [_record(raw) for raw in _plain_list(npc.db.need_rules) if _record(raw)],
        "sites": sites,
        "candidates": collect_need_candidates(npc),
    }
