EXIT_STATE_GATE_BUILD = "0.46.0-state-driven-exits"
EXIT_STATE_OPERATORS = {"EQ", "NE", "GTE", "LTE", "EXISTS", "NOT_EXISTS"}


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


def exit_state_requirements(exit_obj):
    """Normalize authored source-room world_state requirements declared on an exit."""
    output = []
    if not exit_obj:
        return output
    for raw in _plain_list(getattr(exit_obj.db, "state_requirements", [])):
        item = _record(raw)
        if not item:
            continue
        field = str(item.get("field") or "").strip()
        if not field:
            continue
        op = str(item.get("op") or "EQ").strip().upper()
        if op not in EXIT_STATE_OPERATORS:
            continue
        output.append(
            {
                "field": field,
                "op": op,
                "value": item.get("value"),
                "name": str(item.get("name") or field),
            }
        )
    return output


def _compare(exists, current, op, expected):
    if op == "EXISTS":
        return bool(exists)
    if op == "NOT_EXISTS":
        return not bool(exists)
    if not exists:
        return False
    if op == "EQ":
        return current == expected
    if op == "NE":
        return current != expected
    if op in {"GTE", "LTE"}:
        try:
            left = float(current)
            right = float(expected)
        except (TypeError, ValueError):
            return False
        return left >= right if op == "GTE" else left <= right
    return False


def inspect_exit_state(exit_obj):
    """Evaluate one exit against persistent world_state on its source room."""
    source = getattr(exit_obj, "location", None) if exit_obj else None
    world_state = _plain_dict(getattr(source.db, "world_state", {})) if source else {}
    requirements = exit_state_requirements(exit_obj)
    checks = []
    blockers = []

    for requirement in requirements:
        field = requirement.get("field")
        exists = field in world_state
        current = world_state.get(field)
        met = _compare(exists, current, requirement.get("op"), requirement.get("value"))
        row = {
            **requirement,
            "exists": exists,
            "current": current,
            "met": met,
            "site_dbref": int(source.id) if source else None,
            "site_room_id": str(getattr(source.db, "room_id", "") or "") if source else None,
        }
        checks.append(row)
        if not met:
            blockers.append(row)

    return {
        "build": EXIT_STATE_GATE_BUILD,
        "eligible": not blockers,
        "source_dbref": int(source.id) if source else None,
        "source_room_id": str(getattr(source.db, "room_id", "") or "") if source else None,
        "requirements": requirements,
        "checks": checks,
        "blockers": blockers,
    }
