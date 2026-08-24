from services.action_resolution_engine import action_resolution_history
from services.accumulate_d6_resolution_engine import resolve_pending_object_action_accumulate_d6
from services.confront_d6_resolution_engine import resolve_pending_object_action_confront_d6
from services.direct_d6_resolution_engine import pending_object_actions, resolve_pending_object_action_d6
from services.synchronize_d6_resolution_engine import resolve_pending_object_action_synchronize_d6


PLAYER_ROLL_BUILD = "0.55.0-player-roll-mode-dispatch"


def _pending_action(actor, attempt_id=None):
    wanted = str(attempt_id or "").strip()
    rows = pending_object_actions(actor)
    if wanted:
        return next((row for row in rows if str(row.get("attempt_id") or "") == wanted), None)
    return rows[-1] if rows else None


def _resolution_record(actor, resolution_id):
    wanted = str(resolution_id or "").strip()
    for row in action_resolution_history(actor):
        if str(row.get("resolution_id") or "") == wanted:
            return dict(row)
    return None


def resolve_pending_object_action_roll(
    actor,
    attempt_id=None,
    forced_roll=None,
    forced_target_roll=None,
):
    """Dispatch the caller's pending object action to the authored resolution-mode provider."""
    if not actor:
        return {"status": "NO_ACTOR", "build": PLAYER_ROLL_BUILD}

    action = _pending_action(actor, attempt_id=attempt_id)
    if not action:
        return {
            "status": "NO_PENDING_OBJECT_ACTION",
            "attempt_id": str(attempt_id or "").strip() or None,
            "build": PLAYER_ROLL_BUILD,
        }

    resolution_id = str(action.get("resolution_id") or "").strip()
    resolution = _resolution_record(actor, resolution_id)
    if not resolution:
        return {
            "status": "RESOLUTION_NOT_FOUND",
            "attempt_id": action.get("attempt_id"),
            "resolution_id": resolution_id,
            "build": PLAYER_ROLL_BUILD,
        }

    mode = str(resolution.get("mode") or "").upper().strip()
    if mode == "DIRECT":
        packet = resolve_pending_object_action_d6(
            actor,
            attempt_id=action.get("attempt_id"),
            forced_roll=forced_roll,
        )
        packet["mode"] = "DIRECT"
        packet["dispatch_build"] = PLAYER_ROLL_BUILD
        return packet

    if mode == "ACCUMULATE":
        packet = resolve_pending_object_action_accumulate_d6(
            actor,
            attempt_id=action.get("attempt_id"),
            forced_roll=forced_roll,
        )
        packet["mode"] = "ACCUMULATE"
        packet["dispatch_build"] = PLAYER_ROLL_BUILD
        return packet

    if mode == "CONFRONT":
        packet = resolve_pending_object_action_confront_d6(
            actor,
            attempt_id=action.get("attempt_id"),
            forced_actor_roll=forced_roll,
            forced_target_roll=forced_target_roll,
        )
        packet["mode"] = "CONFRONT"
        packet["dispatch_build"] = PLAYER_ROLL_BUILD
        return packet

    if mode == "SYNCHRONIZE":
        packet = resolve_pending_object_action_synchronize_d6(
            actor,
            attempt_id=action.get("attempt_id"),
            forced_roll=forced_roll,
        )
        packet["mode"] = "SYNCHRONIZE"
        packet["dispatch_build"] = PLAYER_ROLL_BUILD
        return packet

    return {
        "status": "UNSUPPORTED_MODE",
        "mode": mode or None,
        "attempt_id": action.get("attempt_id"),
        "resolution_id": resolution_id,
        "build": PLAYER_ROLL_BUILD,
    }
