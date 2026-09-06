from evennia import search_object


STATE_EFFECT_BUILD = "0.49.0-action-object-state-effects"
ALLOWED_SITE_STATE_NAMESPACES = {
    "world_state",
    "world_event_state",
    "work_state",
}
ALLOWED_OBJECT_STATE_NAMESPACES = {
    "state",
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


def _search_exact_dbref(dbref, missing_reason, not_found_reason):
    try:
        dbref = int(dbref)
    except (TypeError, ValueError):
        return None, missing_reason
    if dbref <= 0:
        return None, missing_reason
    matches = list(search_object(f"#{dbref}"))
    if len(matches) != 1:
        return None, not_found_reason
    return matches[0], None


def _site_from_action(action, spec):
    dbref = (spec or {}).get("site_dbref")
    if dbref is None:
        dbref = (action or {}).get("site_dbref")
    return _search_exact_dbref(dbref, "MISSING_SITE_DBREF", "SITE_NOT_FOUND")


def _object_from_action(action, spec):
    action_dbref = (action or {}).get("object_dbref")
    try:
        action_dbref = int(action_dbref)
    except (TypeError, ValueError):
        return None, "MISSING_OBJECT_DBREF"
    if action_dbref <= 0:
        return None, "MISSING_OBJECT_DBREF"

    explicit_dbref = (spec or {}).get("object_dbref")
    if explicit_dbref is not None:
        try:
            explicit_dbref = int(explicit_dbref)
        except (TypeError, ValueError):
            return None, "BAD_OBJECT_DBREF"
        if explicit_dbref != action_dbref:
            return None, "OBJECT_DBREF_MISMATCH"

    obj, error = _search_exact_dbref(action_dbref, "MISSING_OBJECT_DBREF", "OBJECT_NOT_FOUND")
    if not obj:
        return None, error

    action_object_id = str((action or {}).get("object_id") or "").strip()
    actual_object_id = str(getattr(obj.db, "object_id", "") or "").strip()
    if action_object_id and actual_object_id != action_object_id:
        return None, "OBJECT_ID_MISMATCH"
    return obj, None


def _target_from_action(action, spec):
    scope = str((spec or {}).get("scope") or "ACTION_SITE").upper().strip()
    namespace = str((spec or {}).get("namespace") or "").strip()

    if scope == "ACTION_SITE":
        if namespace not in ALLOWED_SITE_STATE_NAMESPACES:
            return None, "NAMESPACE_NOT_ALLOWED", scope
        target, error = _site_from_action(action, spec)
        return target, error, scope

    if scope == "ACTION_OBJECT":
        if namespace not in ALLOWED_OBJECT_STATE_NAMESPACES:
            return None, "NAMESPACE_NOT_ALLOWED", scope
        target, error = _object_from_action(action, spec)
        return target, error, scope

    return None, "UNSUPPORTED_SCOPE", scope


def _apply_one(action, raw_spec):
    spec = _record(raw_spec) or {}
    namespace = str(spec.get("namespace") or "").strip()
    field = str(spec.get("field") or "").strip()
    op = str(spec.get("op") or "SET").upper().strip()

    target, target_error, scope = _target_from_action(action, spec)
    if target_error == "NAMESPACE_NOT_ALLOWED":
        return {
            "success": False,
            "reason": target_error,
            "scope": scope,
            "namespace": namespace,
            "field": field or None,
            "op": op,
            "build": STATE_EFFECT_BUILD,
        }
    if target_error == "UNSUPPORTED_SCOPE":
        return {
            "success": False,
            "reason": target_error,
            "scope": scope,
            "namespace": namespace,
            "field": field or None,
            "op": op,
            "build": STATE_EFFECT_BUILD,
        }
    if not field:
        return {
            "success": False,
            "reason": "MISSING_FIELD",
            "scope": scope,
            "namespace": namespace,
            "op": op,
            "build": STATE_EFFECT_BUILD,
        }
    if op not in ALLOWED_STATE_OPS:
        return {
            "success": False,
            "reason": "OP_NOT_ALLOWED",
            "scope": scope,
            "namespace": namespace,
            "field": field,
            "op": op,
            "build": STATE_EFFECT_BUILD,
        }
    if not target:
        return {
            "success": False,
            "reason": target_error,
            "scope": scope,
            "namespace": namespace,
            "field": field,
            "op": op,
            "build": STATE_EFFECT_BUILD,
        }

    state = _plain_dict(getattr(target.db, namespace, {}))
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
                "scope": scope,
                "target": target.key,
                "target_dbref": int(target.id),
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
                    "scope": scope,
                    "target": target.key,
                    "target_dbref": int(target.id),
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
    setattr(target.db, namespace, state)

    result = {
        "success": True,
        "reason": "STATE_MUTATED",
        "scope": scope,
        "target": target.key,
        "target_dbref": int(target.id),
        "namespace": namespace,
        "field": field,
        "op": op,
        "before": before,
        "value": value,
        "after": after,
        "build": STATE_EFFECT_BUILD,
    }
    if scope == "ACTION_SITE":
        result.update(
            {
                "site": target.key,
                "site_dbref": int(target.id),
                "site_room_id": str(getattr(target.db, "room_id", "") or ""),
            }
        )
    elif scope == "ACTION_OBJECT":
        result.update(
            {
                "object": target.key,
                "object_dbref": int(target.id),
                "object_id": str(getattr(target.db, "object_id", "") or ""),
            }
        )
    return result


def apply_state_effects(action, specs):
    """Apply authored state effects once for one matched consequence rule."""
    output = []
    for raw in _plain_list(specs):
        output.append(_apply_one(action or {}, raw))
    return output
