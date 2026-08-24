import random

from services.action_resolution_engine import action_resolution_history
from services.direct_d6_resolution_engine import pending_object_actions
from services.object_action_engine import resolve_object_action


CONFRONT_D6_BUILD = "0.54.0-confront-d6-player-resolution"
CONFRONT_D6_PROVIDER = "SIZA_CONFRONT_D6"


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


def calculate_confront_d6(resolution_record, forced_actor_roll=None, forced_target_roll=None):
    """Calculate one CONFRONT check as opposed d6 + authored stat totals."""
    record = dict(resolution_record or {})
    mode = str(record.get("mode") or "").upper().strip()
    if mode != "CONFRONT":
        return {
            "success": False,
            "status": "UNSUPPORTED_MODE",
            "mode": mode or None,
            "build": CONFRONT_D6_BUILD,
        }

    actor_value = _number(record.get("actor_stat_value"))
    target_value = _number(record.get("target_stat_value"))
    if actor_value is None:
        return {
            "success": False,
            "status": "MISSING_ACTOR_STAT_VALUE",
            "build": CONFRONT_D6_BUILD,
        }
    if target_value is None:
        return {
            "success": False,
            "status": "MISSING_TARGET_STAT_VALUE",
            "build": CONFRONT_D6_BUILD,
        }

    actor_die, actor_forced = _roll_d6(forced_actor_roll)
    target_die, target_forced = _roll_d6(forced_target_roll)
    if actor_die is None or target_die is None:
        return {
            "success": False,
            "status": "BAD_D6_VALUE",
            "build": CONFRONT_D6_BUILD,
        }

    actor_total = actor_value + actor_die
    target_total = target_value + target_die
    if actor_total > target_total:
        outcome = "ACTOR_WIN"
    elif actor_total < target_total:
        outcome = "TARGET_WIN"
    else:
        outcome = "TIE"

    data = {
        "actor_die": actor_die,
        "target_die": target_die,
        "die_sides": 6,
        "actor_stat": record.get("actor_stat"),
        "actor_stat_value": actor_value,
        "actor_total": actor_total,
        "target_name": record.get("target_name"),
        "target_npc_id": record.get("target_npc_id"),
        "target_stat": record.get("target_stat"),
        "target_stat_value": target_value,
        "target_total": target_total,
        "comparison": "actor_total vs target_total",
        "forced_for_validation": bool(actor_forced or target_forced),
        "formula": "d6 + actor_stat vs d6 + target_stat",
        "provider_build": CONFRONT_D6_BUILD,
    }
    return {
        "success": True,
        "status": "CALCULATED",
        "outcome": outcome,
        "provider": CONFRONT_D6_PROVIDER,
        "resolution_data": data,
        **data,
        "build": CONFRONT_D6_BUILD,
    }


def _resolution_record(actor, resolution_id):
    wanted = str(resolution_id or "").strip()
    for row in action_resolution_history(actor):
        if str(row.get("resolution_id") or "") == wanted:
            return dict(row)
    return None


def resolve_pending_object_action_confront_d6(
    actor,
    attempt_id=None,
    forced_actor_roll=None,
    forced_target_roll=None,
):
    """Resolve one pending CONFRONT object action belonging to actor."""
    if not actor:
        return {"status": "NO_ACTOR", "build": CONFRONT_D6_BUILD}

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
            "build": CONFRONT_D6_BUILD,
        }

    resolution_id = str(action.get("resolution_id") or "").strip()
    resolution = _resolution_record(actor, resolution_id)
    if not resolution:
        return {
            "status": "RESOLUTION_NOT_FOUND",
            "attempt_id": action.get("attempt_id"),
            "resolution_id": resolution_id,
            "build": CONFRONT_D6_BUILD,
        }

    calculated = calculate_confront_d6(
        resolution,
        forced_actor_roll=forced_actor_roll,
        forced_target_roll=forced_target_roll,
    )
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
        CONFRONT_D6_PROVIDER,
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
        "actor_die": calculated.get("actor_die"),
        "actor_stat": calculated.get("actor_stat"),
        "actor_stat_value": calculated.get("actor_stat_value"),
        "actor_total": calculated.get("actor_total"),
        "target_die": calculated.get("target_die"),
        "target_name": calculated.get("target_name"),
        "target_npc_id": calculated.get("target_npc_id"),
        "target_stat": calculated.get("target_stat"),
        "target_stat_value": calculated.get("target_stat_value"),
        "target_total": calculated.get("target_total"),
        "resolution_data": calculated.get("resolution_data"),
        "action_result": resolved,
        "build": CONFRONT_D6_BUILD,
    }
