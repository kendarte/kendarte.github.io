OBJECT_VISIBILITY_BUILD = "0.47.0-state-driven-world-objects"
OBJECT_VISIBILITY_OPERATORS = {"EQ", "NE", "GTE", "LTE", "EXISTS", "NOT_EXISTS"}


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


def _normalize_requirement(raw):
    item = _record(raw)
    if not item:
        return None
    field = str(item.get("field") or "").strip()
    if not field:
        return None
    op = str(item.get("op") or "EQ").strip().upper()
    if op not in OBJECT_VISIBILITY_OPERATORS:
        return None
    return {
        "field": field,
        "op": op,
        "value": item.get("value"),
        "name": str(item.get("name") or field),
    }


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


def inspect_object_visibility(obj, site=None):
    """Evaluate optional authored visibility requirements against the containing site's world_state."""
    if not obj:
        return {
            "build": OBJECT_VISIBILITY_BUILD,
            "gated": False,
            "valid": False,
            "visible": False,
            "checks": [],
            "blockers": [],
        }

    source = site or getattr(obj, "location", None)
    raw_requirements = _plain_list(getattr(obj.db, "state_visibility_requirements", []))
    if not raw_requirements:
        return {
            "build": OBJECT_VISIBILITY_BUILD,
            "gated": False,
            "valid": True,
            "visible": True,
            "checks": [],
            "blockers": [],
            "site_dbref": int(source.id) if source else None,
            "site_room_id": str(getattr(source.db, "room_id", "") or "") if source else None,
        }

    requirements = []
    for raw in raw_requirements:
        normalized = _normalize_requirement(raw)
        if not normalized:
            return {
                "build": OBJECT_VISIBILITY_BUILD,
                "gated": True,
                "valid": False,
                "visible": False,
                "checks": [],
                "blockers": [{"kind": "MALFORMED_STATE_VISIBILITY_REQUIREMENT"}],
                "site_dbref": int(source.id) if source else None,
                "site_room_id": str(getattr(source.db, "room_id", "") or "") if source else None,
            }
        requirements.append(normalized)

    world_state = _plain_dict(getattr(source.db, "world_state", {})) if source else {}
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
        "build": OBJECT_VISIBILITY_BUILD,
        "gated": True,
        "valid": True,
        "visible": not blockers,
        "checks": checks,
        "blockers": blockers,
        "site_dbref": int(source.id) if source else None,
        "site_room_id": str(getattr(source.db, "room_id", "") or "") if source else None,
    }


def object_visible_in_world_state(obj, site=None):
    return bool(inspect_object_visibility(obj, site=site).get("visible"))
