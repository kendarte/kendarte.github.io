from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from services.action_resolution_engine import begin_action_resolution, normalize_check_spec, resolve_action_resolution
from services.confront_d6_resolution_engine import calculate_confront_d6, CONFRONT_D6_PROVIDER
from services.consequence_engine import emit_world_action
from services.direct_d6_resolution_engine import calculate_direct_d6, DIRECT_D6_PROVIDER


DM_FREE_ACTION_CHECK_BUILD = "dm-0.1.1-existing-d6-free-action-resolution"
DM_AUTO_PROVIDER = "SIZA_DM_AUTO"
HISTORY_LIMIT = 50


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _resolve_ref(actor, ref):
    wanted = str(ref or "").strip()
    if not actor or not wanted:
        return None
    if wanted == "SELF":
        return actor
    if wanted == "ROOM":
        return getattr(actor, "location", None)
    location = getattr(actor, "location", None)
    candidates = [actor, location]
    candidates.extend(list(getattr(location, "contents", []) or []) if location else [])
    candidates.extend(list(getattr(actor, "contents", []) or []))
    if wanted.startswith("DBREF:"):
        try:
            dbref = int(wanted.split(":", 1)[1])
        except (TypeError, ValueError):
            return None
        return next((obj for obj in candidates if obj is not None and getattr(obj, "id", None) == dbref), None)
    return None


def _opposition_target(actor, step):
    secondary = _resolve_ref(actor, step.get("secondary_ref"))
    primary = _resolve_ref(actor, step.get("primary_ref"))
    if secondary and bool(getattr(secondary.db, "is_npc", False)):
        return secondary
    if primary and bool(getattr(primary.db, "is_npc", False)):
        return primary
    return secondary or primary


def _history(actor):
    if not actor:
        return []
    return [_plain_dict(row) for row in _plain_list(getattr(actor.db, "dm_free_action_history", []))]


def _save_history(actor, record):
    rows = _history(actor)
    rows.append(deepcopy(record))
    actor.db.dm_free_action_history = rows[-HISTORY_LIMIT:]


def _action_packet(actor, step, outcome, provider, resolution=None, raw_player_input=""):
    location = getattr(actor, "location", None)
    primary = _resolve_ref(actor, step.get("primary_ref"))
    secondary = _resolve_ref(actor, step.get("secondary_ref"))
    action_id = f"DM-FREE-{int(actor.id)}-{uuid4().hex[:16].upper()}"
    return {
        "action_id": action_id,
        "action_type": str(step.get("action_type") or "OTHER").upper(),
        "source": "DM_FREE_ACTION",
        "actor_dbref": int(actor.id),
        "actor_name": str(actor.key),
        "actor_npc_id": str(getattr(actor.db, "npc_id", "") or "") or None,
        "site_dbref": int(location.id) if location and getattr(location, "id", None) is not None else None,
        "site_room_id": str(getattr(getattr(location, "db", None), "room_id", "") or "") if location else None,
        "site_name": str(location.key) if location else None,
        "object_dbref": int(primary.id) if primary and not bool(getattr(primary.db, "is_npc", False)) else None,
        "object_id": str(getattr(getattr(primary, "db", None), "object_id", "") or "") if primary else None,
        "target_dbref": int(secondary.id) if secondary and getattr(secondary, "id", None) is not None else (
            int(primary.id) if primary and bool(getattr(primary.db, "is_npc", False)) else None
        ),
        "target_npc_id": str(getattr(getattr(secondary or primary, "db", None), "npc_id", "") or "") or None,
        "target_name": str(getattr(secondary or primary, "key", "")) or None,
        "primary_ref": str(step.get("primary_ref") or "") or None,
        "secondary_ref": str(step.get("secondary_ref") or "") or None,
        "desired_effect": str(step.get("desired_effect") or ""),
        "player_input": str(raw_player_input or ""),
        "outcome": str(outcome or ""),
        "provider": str(provider or ""),
        "resolution_id": (_plain_dict(resolution)).get("resolution_id"),
        "occurrence": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _resolve_existing_d6_check(
    actor,
    row,
    check_spec,
    *,
    raw_player_input="",
    forced_roll=None,
    forced_target_roll=None,
    history_context=None,
    success_status="DM_CHECK_RESOLVED",
):
    """Resolve an already-authorized DIRECT/CONFRONT check without letting AI select the outcome."""
    checked = normalize_check_spec(check_spec)
    if not checked.get("valid"):
        return {
            "status": "INVALID_AUTHORIZED_CHECK",
            "executed": False,
            "check": checked,
            "build": DM_FREE_ACTION_CHECK_BUILD,
        }
    mode = str(checked.get("mode") or "").upper().strip()
    if mode not in {"DIRECT", "CONFRONT"}:
        return {
            "status": "UNSUPPORTED_AUTHORIZED_CHECK_MODE",
            "executed": False,
            "mode": mode,
            "build": DM_FREE_ACTION_CHECK_BUILD,
        }

    target = _opposition_target(actor, row) if mode == "CONFRONT" else None
    resolution_id = f"DM-RES-{uuid4().hex}"
    prepared = begin_action_resolution(actor, checked, target=target, resolution_id=resolution_id)
    if str(prepared.get("status") or "") != "PENDING_RESOLUTION":
        return {
            "status": "CHECK_PREPARATION_BLOCKED",
            "executed": False,
            "preparation": prepared,
            "build": DM_FREE_ACTION_CHECK_BUILD,
        }

    if mode == "DIRECT":
        calculated = calculate_direct_d6(prepared, forced_roll=forced_roll)
        provider = DIRECT_D6_PROVIDER
    else:
        calculated = calculate_confront_d6(
            prepared,
            forced_actor_roll=forced_roll,
            forced_target_roll=forced_target_roll,
        )
        provider = CONFRONT_D6_PROVIDER
    if not calculated.get("success"):
        return {
            "status": "CHECK_CALCULATION_FAILED",
            "executed": False,
            "resolution_id": resolution_id,
            "calculation": calculated,
            "build": DM_FREE_ACTION_CHECK_BUILD,
        }

    outcome = str(calculated.get("outcome") or "")
    persisted = resolve_action_resolution(
        actor,
        resolution_id,
        outcome,
        provider,
        resolution_data=calculated.get("resolution_data"),
    )
    if str(persisted.get("status") or "") != "RESOLVED":
        return {
            "status": "CHECK_PERSIST_FAILED",
            "executed": False,
            "resolution_id": resolution_id,
            "calculation": calculated,
            "persisted": persisted,
            "build": DM_FREE_ACTION_CHECK_BUILD,
        }

    action = _action_packet(actor, row, outcome, provider, resolution=persisted, raw_player_input=raw_player_input)
    consequence = emit_world_action(action)
    history_record = {
        "status": "RESOLVED",
        "action": action,
        "resolution_context": deepcopy(_plain_dict(history_context)),
        "resolution": persisted,
        "calculation": calculated,
        "consequence": consequence,
        "build": DM_FREE_ACTION_CHECK_BUILD,
    }
    _save_history(actor, history_record)
    return {
        "status": success_status,
        "executed": True,
        "outcome": outcome,
        "provider": provider,
        "action": action,
        "resolution": persisted,
        "calculation": calculated,
        "consequence": consequence,
        "rendered_text": "",
        "build": DM_FREE_ACTION_CHECK_BUILD,
    }


def resolve_judged_dm_check(
    actor,
    step,
    *,
    raw_player_input="",
    forced_roll=None,
    forced_target_roll=None,
):
    """Resolve one DM_CHECK using only existing World Engine check preparation and d6 providers."""
    row = _plain_dict(step)
    if str(row.get("executor") or "") != "DM_CHECK":
        return {"status": "NOT_DM_CHECK", "executed": False, "build": DM_FREE_ACTION_CHECK_BUILD}
    judgment = _plain_dict(row.get("judgment"))
    mode = str(judgment.get("mode") or "").upper().strip()
    if mode not in {"DIRECT", "CONFRONT"}:
        return {"status": "UNSUPPORTED_JUDGED_MODE", "executed": False, "mode": mode, "build": DM_FREE_ACTION_CHECK_BUILD}

    check_spec = {
        "id": f"DM-CHECK-{uuid4().hex[:16].upper()}",
        "trigger": "OPPOSITION" if mode == "CONFRONT" else "OBSTACLE",
        "mode": mode,
        "stat": judgment.get("actor_stat"),
        "target_stat": judgment.get("target_stat") if mode == "CONFRONT" else None,
        "difficulty": judgment.get("difficulty") if mode == "DIRECT" else None,
        "metadata": {
            "source": "DM_FREE_ACTION",
            "action_type": row.get("action_type"),
            "desired_effect": row.get("desired_effect"),
            "difficulty_tier": judgment.get("difficulty_tier"),
            "dm_reason": judgment.get("reason"),
        },
    }
    return _resolve_existing_d6_check(
        actor,
        row,
        check_spec,
        raw_player_input=raw_player_input,
        forced_roll=forced_roll,
        forced_target_roll=forced_target_roll,
        history_context={"kind": "DM_JUDGMENT", "judgment": judgment},
        success_status="DM_CHECK_RESOLVED",
    )


def resolve_authored_dm_check(
    actor,
    step,
    *,
    raw_player_input="",
    forced_roll=None,
    forced_target_roll=None,
):
    """Resolve one authored DM affordance check exactly as defined by world data; the Judge is bypassed."""
    row = _plain_dict(step)
    if str(row.get("executor") or "") != "AUTHORED_CHECK":
        return {"status": "NOT_AUTHORED_CHECK", "executed": False, "build": DM_FREE_ACTION_CHECK_BUILD}
    check_spec = _plain_dict(row.get("authoritative_check"))
    if not check_spec:
        return {"status": "MISSING_AUTHORED_CHECK", "executed": False, "build": DM_FREE_ACTION_CHECK_BUILD}
    return _resolve_existing_d6_check(
        actor,
        row,
        check_spec,
        raw_player_input=raw_player_input,
        forced_roll=forced_roll,
        forced_target_roll=forced_target_roll,
        history_context={
            "kind": "AUTHORED_AFFORDANCE_CHECK",
            "affordance": _plain_dict(row.get("affordance")),
            "authoritative_check": check_spec,
        },
        success_status="AUTHORED_CHECK_RESOLVED",
    )


def resolve_judged_dm_auto(actor, step, *, raw_player_input=""):
    """Record an automatic verified action as world input without a dice check."""
    row = _plain_dict(step)
    if str(row.get("executor") or "") != "DM_AUTO":
        return {"status": "NOT_DM_AUTO", "executed": False, "build": DM_FREE_ACTION_CHECK_BUILD}
    action = _action_packet(actor, row, "SUCCESS", DM_AUTO_PROVIDER, raw_player_input=raw_player_input)
    consequence = emit_world_action(action)
    history_record = {
        "status": "RESOLVED",
        "action": action,
        "resolution_context": {"kind": "DM_AUTO", "judgment": _plain_dict(row.get("judgment"))},
        "resolution": None,
        "calculation": None,
        "consequence": consequence,
        "build": DM_FREE_ACTION_CHECK_BUILD,
    }
    _save_history(actor, history_record)
    return {
        "status": "DM_AUTO_RESOLVED",
        "executed": True,
        "outcome": "SUCCESS",
        "provider": DM_AUTO_PROVIDER,
        "action": action,
        "consequence": consequence,
        "rendered_text": "",
        "build": DM_FREE_ACTION_CHECK_BUILD,
    }
