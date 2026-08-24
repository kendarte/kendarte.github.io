from evennia import search_object


STATE_EFFECT_BUILD = "0.43.0-outcome-state-effects"
ALLOWED_STATE_NAMESPACES = {
    "world_state",
    "world_event_state",
    "work_state",
}
ALLOWED_STATE_OPS = {
    "SET",
    "ADD",
    "SUBTRACT",
    "MAX",
    "MIN",
}


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


def _number(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    try:
        text = str(value).strip()
        return float(text) if "." in text else int(text)
    except (TypeError, ValueError):
        return None


def _site_from_action(action, spec):
    scope = str((spec or {}).get("scope") or "ACTION_SITE").upper()
    if scope != "ACTION_SITE":
        return None, "UNSUPPORTED_SCOPE"

    dbref = (spec or {}).get("site_dbref")
    if dbref is None:
        dbref = (action or {}).get("site_dbref")
    try:
        dbref = int(dbref)
    except (TypeError, ValueError):
        return None, "MISSING_SITE_DBREF"
    if dbref <= 0:
        return None, "MISSING_SITE_DBREF"

    matches = list(search_object(f"#{dbref}"))
    if len(matches) != 1:
        return None, "SITE_NOT_FOUND"
    return matches[0], None


def _apply_one(action, raw_spec):
    spec = _record(raw_spec) or {}
    namespace = str(spec.get("namespace") or "").strip()
    field = str(spec.get("field") or "").strip()
    op = str(spec.get("op") or "SET").upper().strip()

    if namespace not in ALLOWED_STATE_NAMESPACES:
        return {
            "success": False,
            "reason": "NAMESPACE_NOT_ALLOWED",
            "namespace": namespace,
            "field": field or None,
            "op": op,
            "build": STATE_EFFECT_BUILD,
        }
    if not field:
        return {
            "success": False,
            "reason": "MISSING_FIELD",
            "namespace": namespace,
            "op": op,
            "build": STATE_EFFECT_BUILD,
        }
    if op not in ALLOWED_STATE_OPS:
        return {
            "success": False,
            "reason": "OP_NOT_ALLOWED",
            "namespace": namespace,
            "field": field,
            "op": op,
            "build": STATE_EFFECT_BUILD,
        }

    site, error = _site_from_action(action, spec)
    if not site:
        return {
            "success": False,
            "reason": error,
            "namespace": namespace,
            "field": field,
            "op": op,
            "build": STATE_EFFECT_BUILD,
        }

    state = _plain_dict(getattr(site.db, namespace, {}))
    before = state.get(field)
    value = spec.get("value")

    if op == "SET":
        after = value
    else:
        numeric_value = _number(value)
        numeric_before = _number(before)
        if numeric_value is None:
            return {
                "success": False,
                "reason": "VALUE_NOT_NUMERIC",
                "site": site.key,
                "site_dbref": int(site.id),
                "namespace": namespace,
                "field": field,
                "op": op,
                "before": before,
                "value": value,
                "build": STATE_EFFECT_BUILD,
            }
        if numeric_before is None:
            if before is not None:
                return {
                    "success": False,
                    "reason": "CURRENT_NOT_NUMERIC",
                    "site": site.key,
                    "site_dbref": int(site.id),
                    "namespace": namespace,
                    "field": field,
                    "op": op,
                    "before": before,
                    "value": value,
                    "build": STATE_EFFECT_BUILD,
                }
            numeric_before = 0

        if op == "ADD":
            after = numeric_before + numeric_value
        elif op == "SUBTRACT":
            after = numeric_before - numeric_value
        elif op == "MAX":
            after = max(numeric_before, numeric_value)
        else:
            after = min(numeric_before, numeric_value)

    state[field] = after
    setattr(site.db, namespace, state)
    return {
        "success": True,
        "reason": "STATE_MUTATED",
        "site": site.key,
        "site_dbref": int(site.id),
        "site_room_id": str(getattr(site.db, "room_id", "") or ""),
        "namespace": namespace,
        "field": field,
        "op": op,
        "before": before,
        "value": value,
        "after": after,
        "build": STATE_EFFECT_BUILD,
    }


def apply_state_effects(action, specs):
    """Apply authored state effects once for one matched consequence rule."""
    output = []
    for raw in _plain_list(specs):
        output.append(_apply_one(action or {}, raw))
    return output
