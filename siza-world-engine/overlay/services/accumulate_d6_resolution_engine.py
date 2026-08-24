import random

from evennia import search_object

from services.action_resolution_engine import action_resolution_history
from services.object_action_engine import object_action_history, resolve_object_action


ACCUMULATE_D6_BUILD = "0.53.0-accumulate-d6-player-resolution"
ACCUMULATE_D6_PROVIDER = "SIZA_ACCUMULATE_D6"


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


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


def _roll_d6(forced_roll=None):
    if forced_roll is None:
        return random.SystemRandom().randint(1, 6), False
    try:
        value = int(forced_roll)
    except (TypeError, ValueError):
        return None, True
    if value < 1 or value > 6:
        return None, True
    return value, True


def _resolution_record(actor, resolution_id):
    wanted = str(resolution_id or "").strip()
    for row in action_resolution_history(actor):
        if str(row.get("resolution_id") or "") == wanted:
            return dict(row)
    return None


def _pending_object_action(actor, attempt_id=None):
    wanted = str(attempt_id or "").strip()
    rows = []
    for row in object_action_history(actor):
        if str(row.get("status") or "") != "PENDING_RESOLUTION":
            continue
        if bool(row.get("resolved")):
            continue
        if not str(row.get("resolution_id") or "").strip():
            continue
        rows.append(dict(row))
    if wanted:
        return next((row for row in rows if str(row.get("attempt_id") or "") == wanted), None)
    return rows[-1] if rows else None


def _action_object(action):
    try:
        dbref = int((action or {}).get("object_dbref"))
    except (TypeError, ValueError):
        return None, "MISSING_OBJECT_DBREF"
    if dbref <= 0:
        return None, "MISSING_OBJECT_DBREF"
    matches = list(search_object(f"#{dbref}"))
    if len(matches) != 1:
        return None, "OBJECT_NOT_FOUND"
    obj = matches[0]
    expected_id = str((action or {}).get("object_id") or "").strip()
    actual_id = str(getattr(obj.db, "object_id", "") or "").strip()
    if expected_id and expected_id != actual_id:
        return None, "OBJECT_ID_MISMATCH"
    return obj, None


def calculate_accumulate_d6(resolution_record, obj, forced_roll=None):
    """Resolve one ACCUMULATE attempt from authored persistent object progress metadata."""
    record = dict(resolution_record or {})
    mode = str(record.get("mode") or "").upper().strip()
    if mode != "ACCUMULATE":
        return {
            "success": False,
            "status": "UNSUPPORTED_MODE",
            "mode": mode or None,
            "build": ACCUMULATE_D6_BUILD,
        }
    if not obj:
        return {"success": False, "status": "NO_OBJECT", "build": ACCUMULATE_D6_BUILD}

    stat_value = _number(record.get("actor_stat_value"))
    difficulty = _number(record.get("difficulty"))
    if stat_value is None:
        return {"success": False, "status": "MISSING_ACTOR_STAT_VALUE", "build": ACCUMULATE_D6_BUILD}
    if difficulty is None:
        return {"success": False, "status": "MISSING_DIFFICULTY", "build": ACCUMULATE_D6_BUILD}

    metadata = _plain_dict(record.get("metadata"))
    progress_field = str(metadata.get("progress_field") or "").strip()
    goal = _number(metadata.get("progress_goal"))
    step = _number(metadata.get("progress_step", 1))
    if not progress_field:
        return {"success": False, "status": "MISSING_PROGRESS_FIELD", "build": ACCUMULATE_D6_BUILD}
    if goal is None or goal <= 0:
        return {"success": False, "status": "BAD_PROGRESS_GOAL", "build": ACCUMULATE_D6_BUILD}
    if step is None or step <= 0:
        return {"success": False, "status": "BAD_PROGRESS_STEP", "build": ACCUMULATE_D6_BUILD}

    state = _plain_dict(getattr(obj.db, "state", {}))
    if progress_field not in state:
        return {
            "success": False,
            "status": "MISSING_PROGRESS_STATE",
            "progress_field": progress_field,
            "build": ACCUMULATE_D6_BUILD,
        }
    progress_before = _number(state.get(progress_field))
    if progress_before is None:
        return {
            "success": False,
            "status": "BAD_PROGRESS_STATE",
            "progress_field": progress_field,
            "build": ACCUMULATE_D6_BUILD,
        }

    die, forced = _roll_d6(forced_roll)
    if die is None:
        return {"success": False, "status": "BAD_D6_VALUE", "build": ACCUMULATE_D6_BUILD}

    total = stat_value + die
    passed = total >= difficulty
    if passed:
        projected = min(goal, progress_before + step)
        outcome = "COMPLETE" if projected >= goal else "PROGRESS"
    else:
        projected = max(0, progress_before - step)
        outcome = "SETBACK" if progress_before > 0 else "FAILURE"

    data = {
        "die": die,
        "die_sides": 6,
        "actor_stat": record.get("actor_stat"),
        "actor_stat_value": stat_value,
        "total": total,
        "difficulty": difficulty,
        "comparison": ">=",
        "forced_for_validation": bool(forced),
        "formula": "d6 + actor_stat >= difficulty",
        "progress_field": progress_field,
        "progress_before": progress_before,
        "progress_projected": projected,
        "progress_goal": goal,
        "progress_step": step,
        "provider_build": ACCUMULATE_D6_BUILD,
    }
    return {
        "success": True,
        "status": "CALCULATED",
        "outcome": outcome,
        "provider": ACCUMULATE_D6_PROVIDER,
        "resolution_data": data,
        **data,
        "build": ACCUMULATE_D6_BUILD,
    }


def resolve_pending_object_action_accumulate_d6(actor, attempt_id=None, forced_roll=None):
    """Resolve one pending ACCUMULATE object-action attempt and let consequences persist its progress."""
    if not actor:
        return {"status": "NO_ACTOR", "build": ACCUMULATE_D6_BUILD}

    action = _pending_object_action(actor, attempt_id=attempt_id)
    if not action:
        return {
            "status": "NO_PENDING_OBJECT_ACTION",
            "attempt_id": str(attempt_id or "").strip() or None,
            "build": ACCUMULATE_D6_BUILD,
        }

    resolution_id = str(action.get("resolution_id") or "").strip()
    resolution = _resolution_record(actor, resolution_id)
    if not resolution:
        return {
            "status": "RESOLUTION_NOT_FOUND",
            "attempt_id": action.get("attempt_id"),
            "resolution_id": resolution_id,
            "build": ACCUMULATE_D6_BUILD,
        }

    obj, error = _action_object(action)
    if not obj:
        return {
            "status": error,
            "attempt_id": action.get("attempt_id"),
            "resolution_id": resolution_id,
            "build": ACCUMULATE_D6_BUILD,
        }

    calculated = calculate_accumulate_d6(resolution, obj, forced_roll=forced_roll)
    if not calculated.get("success"):
        return {
            **calculated,
            "attempt_id": action.get("attempt_id"),
            "resolution_id": resolution_id,
            "object_action_id": action.get("object_action_id"),
            "object_action_name": action.get("object_action_name"),
        }

    resolved = resolve_object_action(
        actor,
        action.get("attempt_id"),
        calculated.get("outcome"),
        ACCUMULATE_D6_PROVIDER,
        resolution_data=calculated.get("resolution_data"),
    )
    state_after = _plain_dict(getattr(obj.db, "state", {}))
    progress_after = state_after.get(calculated.get("progress_field"))
    return {
        "status": resolved.get("status"),
        "mode": "ACCUMULATE",
        "outcome": resolved.get("outcome"),
        "provider": resolved.get("provider"),
        "attempt_id": action.get("attempt_id"),
        "resolution_id": resolution_id,
        "object_action_id": action.get("object_action_id"),
        "object_action_name": action.get("object_action_name"),
        "object_id": action.get("object_id"),
        "object_dbref": action.get("object_dbref"),
        "die": calculated.get("die"),
        "actor_stat": calculated.get("actor_stat"),
        "actor_stat_value": calculated.get("actor_stat_value"),
        "total": calculated.get("total"),
        "difficulty": calculated.get("difficulty"),
        "progress_field": calculated.get("progress_field"),
        "progress_before": calculated.get("progress_before"),
        "progress_projected": calculated.get("progress_projected"),
        "progress_after": progress_after,
        "progress_goal": calculated.get("progress_goal"),
        "resolution_data": calculated.get("resolution_data"),
        "action_result": resolved,
        "build": ACCUMULATE_D6_BUILD,
    }
