import random

from services.action_resolution_engine import action_resolution_history
from services.object_action_engine import object_action_history, resolve_object_action


DIRECT_D6_BUILD = "0.52.0-direct-d6-player-resolution"
DIRECT_D6_PROVIDER = "SIZA_DIRECT_D6"


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


def calculate_direct_d6(resolution_record, forced_roll=None):
    """Calculate one authored DIRECT check as d6 + actor stat against authored difficulty."""
    record = dict(resolution_record or {})
    mode = str(record.get("mode") or "").upper().strip()
    if mode != "DIRECT":
        return {
            "success": False,
            "status": "UNSUPPORTED_MODE",
            "mode": mode or None,
            "build": DIRECT_D6_BUILD,
        }

    stat_value = _number(record.get("actor_stat_value"))
    difficulty = _number(record.get("difficulty"))
    if stat_value is None:
        return {
            "success": False,
            "status": "MISSING_ACTOR_STAT_VALUE",
            "build": DIRECT_D6_BUILD,
        }
    if difficulty is None:
        return {
            "success": False,
            "status": "MISSING_DIFFICULTY",
            "build": DIRECT_D6_BUILD,
        }

    die, forced = _roll_d6(forced_roll)
    if die is None:
        return {
            "success": False,
            "status": "BAD_D6_VALUE",
            "build": DIRECT_D6_BUILD,
        }

    total = stat_value + die
    outcome = "SUCCESS" if total >= difficulty else "FAILURE"
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
        "provider_build": DIRECT_D6_BUILD,
    }
    return {
        "success": True,
        "status": "CALCULATED",
        "outcome": outcome,
        "provider": DIRECT_D6_PROVIDER,
        "resolution_data": data,
        **data,
        "build": DIRECT_D6_BUILD,
    }


def _resolution_record(actor, resolution_id):
    wanted = str(resolution_id or "").strip()
    for row in action_resolution_history(actor):
        if str(row.get("resolution_id") or "") == wanted:
            return dict(row)
    return None


def pending_object_actions(actor):
    output = []
    for row in object_action_history(actor):
        if str(row.get("status") or "") != "PENDING_RESOLUTION":
            continue
        if bool(row.get("resolved")):
            continue
        if not str(row.get("resolution_id") or "").strip():
            continue
        output.append(dict(row))
    return output


def resolve_pending_object_action_d6(actor, attempt_id=None, forced_roll=None):
    """Resolve one pending DIRECT object action belonging to actor using the Siza d6 provider."""
    if not actor:
        return {"status": "NO_ACTOR", "build": DIRECT_D6_BUILD}

    wanted = str(attempt_id or "").strip()
    pending = pending_object_actions(actor)
    if wanted:
        action = next(
            (row for row in pending if str(row.get("attempt_id") or "") == wanted),
            None,
        )
    else:
        action = pending[-1] if pending else None

    if not action:
        return {
            "status": "NO_PENDING_OBJECT_ACTION",
            "attempt_id": wanted or None,
            "build": DIRECT_D6_BUILD,
        }

    resolution_id = str(action.get("resolution_id") or "").strip()
    resolution = _resolution_record(actor, resolution_id)
    if not resolution:
        return {
            "status": "RESOLUTION_NOT_FOUND",
            "attempt_id": action.get("attempt_id"),
            "resolution_id": resolution_id,
            "build": DIRECT_D6_BUILD,
        }

    calculated = calculate_direct_d6(resolution, forced_roll=forced_roll)
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
        DIRECT_D6_PROVIDER,
        resolution_data=calculated.get("resolution_data"),
    )
    return {
        "status": resolved.get("status"),
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
        "resolution_data": calculated.get("resolution_data"),
        "action_result": resolved,
        "build": DIRECT_D6_BUILD,
    }
