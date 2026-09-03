from datetime import datetime, timezone
from uuid import uuid4

from services.action_requirement_engine import check_action_requirements
from services.action_resolution_engine import (
    action_requires_resolution,
    begin_action_resolution,
    resolve_action_resolution,
)
from services.consequence_engine import emit_world_action
from services.object_visibility_engine import object_visible_in_world_state


OBJECT_ACTION_BUILD = "0.48.1-campaign-observed-object-actions"
OBJECT_ACTION_HISTORY_LIMIT = 50
OBJECT_STATE_OPERATORS = {"EQ", "NE", "GTE", "LTE", "EXISTS", "NOT_EXISTS"}


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


def _normalize_object_state_requirement(raw):
    item = _record(raw)
    if not item:
        return None
    field = str(item.get("field") or "").strip()
    if not field:
        return None
    op = str(item.get("op") or "EQ").strip().upper()
    if op not in OBJECT_STATE_OPERATORS:
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


def authored_object_actions(obj):
    """Return normalized authored actions declared on one persistent WorldObject."""
    output = []
    if not obj:
        return output
    for raw in _plain_list(getattr(obj.db, "object_actions", [])):
        item = _record(raw)
        if not item:
            continue
        action_id = str(item.get("id") or "").strip()
        if not action_id:
            continue
        malformed = False
        object_state_requirements = []
        for requirement in _plain_list(item.get("object_state_requirements")):
            normalized = _normalize_object_state_requirement(requirement)
            if not normalized:
                malformed = True
                break
            object_state_requirements.append(normalized)
        item["id"] = action_id
        item["enabled"] = bool(item.get("enabled", True))
        item.setdefault("name", action_id)
        item.setdefault("activity", item.get("name") or action_id)
        item.setdefault("canon_status", "prototype")
        item["metadata"] = _plain_dict(item.get("metadata"))
        item["skill_requirements"] = [
            _plain_dict(row) for row in _plain_list(item.get("skill_requirements"))
        ]
        item["knowledge_requirements"] = [
            _plain_dict(row) for row in _plain_list(item.get("knowledge_requirements"))
        ]
        item["state_requirements"] = [
            _plain_dict(row) for row in _plain_list(item.get("state_requirements"))
        ]
        item["object_state_requirements"] = object_state_requirements
        item["valid"] = not malformed
        if item.get("check") is not None:
            item["check"] = _plain_dict(item.get("check"))
        output.append(item)
    return output


def _object_state_check(obj, action):
    state = _plain_dict(getattr(obj.db, "state", {})) if obj else {}
    checks = []
    blockers = []
    if not bool((action or {}).get("valid", True)):
        return {
            "eligible": False,
            "checks": [],
            "blockers": [{"kind": "MALFORMED_OBJECT_STATE_REQUIREMENT"}],
        }
    for requirement in (action or {}).get("object_state_requirements") or []:
        field = requirement.get("field")
        exists = field in state
        current = state.get(field)
        met = _compare(exists, current, requirement.get("op"), requirement.get("value"))
        row = {
            **requirement,
            "exists": exists,
            "current": current,
            "met": met,
            "object_dbref": int(obj.id) if obj else None,
            "object_id": str(getattr(obj.db, "object_id", "") or "") if obj else None,
        }
        checks.append(row)
        if not met:
            blockers.append(
                {
                    "kind": "OBJECT_STATE",
                    "id": field,
                    "name": requirement.get("name"),
                    "op": requirement.get("op"),
                    "current": current,
                    "exists": exists,
                    "required": requirement.get("value"),
                    "object_dbref": int(obj.id) if obj else None,
                    "object_id": str(getattr(obj.db, "object_id", "") or "") if obj else None,
                }
            )
    return {"eligible": not blockers, "checks": checks, "blockers": blockers}


def inspect_object_actions(actor, obj):
    """Inspect enabled object actions without hiding blockers from admin/debug consumers."""
    output = []
    actor_site = getattr(actor, "location", None) if actor else None
    obj_site = getattr(obj, "location", None) if obj else None
    local = bool(actor_site and obj_site and actor_site == obj_site)
    visible = bool(local and object_visible_in_world_state(obj, site=actor_site)) if obj else False

    for action in authored_object_actions(obj):
        if not bool(action.get("enabled", True)):
            continue
        item = dict(action)
        actor_check = check_action_requirements(actor, action) if actor else {
            "eligible": False,
            "blockers": [{"kind": "NO_ACTOR"}],
        }
        object_check = _object_state_check(obj, action)
        blockers = []
        if not local:
            blockers.append({"kind": "OBJECT_NOT_LOCAL"})
        elif not visible:
            blockers.append({"kind": "OBJECT_NOT_VISIBLE"})
        blockers.extend(list(actor_check.get("blockers") or []))
        blockers.extend(list(object_check.get("blockers") or []))
        item["actor_requirement_check"] = actor_check
        item["object_state_check"] = object_check
        item["local"] = local
        item["visible"] = visible
        item["blockers"] = blockers
        item["eligible"] = not blockers
        item["object_id"] = str(getattr(obj.db, "object_id", "") or "") if obj else None
        item["object_dbref"] = int(obj.id) if obj else None
        output.append(item)
    return output


def available_object_actions(actor, obj):
    return [row for row in inspect_object_actions(actor, obj) if bool(row.get("eligible"))]


def find_object_action(actor, obj, action_id, eligible_only=True):
    wanted = str(action_id or "").strip()
    if not wanted:
        return None
    rows = available_object_actions(actor, obj) if eligible_only else inspect_object_actions(actor, obj)
    return next((row for row in rows if str(row.get("id") or "") == wanted), None)


def object_action_history(actor):
    output = []
    if not actor:
        return output
    for raw in _plain_list(getattr(actor.db, "object_action_history", [])):
        item = _record(raw)
        if item and item.get("attempt_id"):
            output.append(item)
    return output


def _save_history(actor, history):
    actor.db.object_action_history = list(history)[-OBJECT_ACTION_HISTORY_LIMIT:]


def _actor_npc_id(actor):
    return str(getattr(actor.db, "npc_id", "") or "").strip() if actor else ""


def _site_payload(actor):
    site = getattr(actor, "location", None)
    return {
        "site_name": site.key if site else None,
        "site_room_id": str(getattr(site.db, "room_id", "") or "") if site else None,
        "site_dbref": int(site.id) if site else None,
    }


def _object_payload(obj):
    return {
        "object_name": obj.key if obj else None,
        "object_id": str(getattr(obj.db, "object_id", "") or "") if obj else None,
        "object_dbref": int(obj.id) if obj else None,
    }


def _observe_campaign_object_action(actor, record):
    """Publish only a completed authoritative object action to the active campaign."""
    from services.dm_campaign_registry import observe_active_campaign_evidence

    return observe_active_campaign_evidence(
        actor,
        {
            "authority": "WORLD_ENGINE",
            "source": "OBJECT_ACTION_ENGINE",
            "action_types": ["OBJECT_ACTION_EXECUTED"],
            "result": {
                "attempt_id": record.get("attempt_id"),
                "object_action_id": record.get("object_action_id"),
                "object_action_name": record.get("object_action_name"),
                "status": record.get("status"),
                "outcome": record.get("outcome"),
                "provider": record.get("provider"),
                "site_dbref": record.get("site_dbref"),
                "site_room_id": record.get("site_room_id"),
                "object_dbref": record.get("object_dbref"),
                "object_id": record.get("object_id"),
            },
        },
    )


def begin_object_action(actor, obj, action_id, attempt_id=None):
    """Start one authored action on a local visible object using existing hard gates and resolution lifecycle."""
    if not actor:
        return {"status": "NO_ACTOR", "build": OBJECT_ACTION_BUILD}
    if not obj:
        return {"status": "NO_OBJECT", "build": OBJECT_ACTION_BUILD}
    if not getattr(actor, "location", None):
        return {"status": "NO_LOCATION", "build": OBJECT_ACTION_BUILD}
    if getattr(obj, "location", None) != actor.location:
        return {"status": "OBJECT_NOT_LOCAL", "build": OBJECT_ACTION_BUILD, **_object_payload(obj)}
    if not object_visible_in_world_state(obj, site=actor.location):
        return {"status": "OBJECT_NOT_VISIBLE", "build": OBJECT_ACTION_BUILD, **_object_payload(obj)}

    action = find_object_action(actor, obj, action_id, eligible_only=False)
    if not action:
        return {
            "status": "OBJECT_ACTION_NOT_AVAILABLE",
            "object_action_id": str(action_id or "").strip(),
            "build": OBJECT_ACTION_BUILD,
            **_object_payload(obj),
        }
    if not bool(action.get("eligible")):
        return {
            "status": "OBJECT_ACTION_REQUIREMENTS_UNMET",
            "object_action_id": action.get("id"),
            "object_action_name": action.get("name"),
            "blockers": list(action.get("blockers") or []),
            "actor_requirement_check": action.get("actor_requirement_check"),
            "object_state_check": action.get("object_state_check"),
            "build": OBJECT_ACTION_BUILD,
            **_site_payload(actor),
            **_object_payload(obj),
        }

    attempt_id = str(attempt_id or "").strip() or f"OACT-{uuid4().hex}"
    history = object_action_history(actor)
    if any(str(row.get("attempt_id") or "") == attempt_id for row in history):
        return {"status": "DUPLICATE_ATTEMPT_ID", "attempt_id": attempt_id, "build": OBJECT_ACTION_BUILD}

    now = datetime.now(timezone.utc).isoformat()
    record = {
        "attempt_id": attempt_id,
        "object_action_id": action.get("id"),
        "object_action_name": action.get("name"),
        "activity": action.get("activity"),
        "canon_status": action.get("canon_status") or "prototype",
        "actor_npc_id": _actor_npc_id(actor),
        "actor_name": actor.key,
        "created_at": now,
        "metadata": _plain_dict(action.get("metadata")),
        "actor_requirement_check": action.get("actor_requirement_check"),
        "object_state_check": action.get("object_state_check"),
        "build": OBJECT_ACTION_BUILD,
        **_site_payload(actor),
        **_object_payload(obj),
    }

    if action_requires_resolution(action):
        resolution_id = f"{attempt_id}:RESOLUTION"
        resolution = begin_action_resolution(actor, action.get("check") or {}, target=obj, resolution_id=resolution_id)
        if str(resolution.get("status") or "") != "PENDING_RESOLUTION":
            record.update(
                {
                    "status": "BLOCKED_CHECK",
                    "resolved": False,
                    "outcome": None,
                    "resolution_id": resolution_id,
                    "resolution_status": resolution.get("status"),
                    "resolution_packet": _plain_dict(resolution),
                }
            )
            history.append(record)
            _save_history(actor, history)
            return dict(record)
        record.update(
            {
                "status": "PENDING_RESOLUTION",
                "resolved": False,
                "outcome": None,
                "resolution_id": resolution_id,
                "resolution_mode": resolution.get("mode"),
                "resolution_trigger": resolution.get("trigger"),
                "actor_stat": resolution.get("actor_stat"),
                "actor_stat_value": resolution.get("actor_stat_value"),
                "difficulty": resolution.get("difficulty"),
            }
        )
        history.append(record)
        _save_history(actor, history)
        return dict(record)

    record.update(
        {
            "status": "COMPLETED",
            "resolved": True,
            "outcome": "COMPLETED",
            "completed_at": now,
            "resolution_id": None,
        }
    )
    consequence = emit_world_action(
        {
            "action_id": f"OBJECT_ACTION_COMPLETED:{attempt_id}",
            "action_type": "OBJECT_ACTION_COMPLETED",
            "actor_npc_id": _actor_npc_id(actor),
            "actor_name": actor.key,
            "object_action_id": action.get("id"),
            "attempt_id": attempt_id,
            "outcome": "COMPLETED",
            "recipient_ids": [_actor_npc_id(actor)] if _actor_npc_id(actor) else [],
            **_site_payload(actor),
            **_object_payload(obj),
        }
    )
    record["action_consequence"] = consequence
    history.append(record)
    _save_history(actor, history)
    return {
        **dict(record),
        "campaign_observation": _observe_campaign_object_action(actor, record),
    }


def resolve_object_action(actor, attempt_id, outcome, provider, resolution_data=None):
    """Resolve one pending object action and emit it through the existing Consequence Engine."""
    if not actor:
        return {"status": "NO_ACTOR", "build": OBJECT_ACTION_BUILD}
    wanted = str(attempt_id or "").strip()
    history = object_action_history(actor)

    for index, current in enumerate(history):
        if str(current.get("attempt_id") or "") != wanted:
            continue
        record = dict(current)
        if bool(record.get("resolved")) or str(record.get("status") or "") in {"RESOLVED", "COMPLETED"}:
            return {
                "status": "ALREADY_RESOLVED",
                "attempt_id": wanted,
                "outcome": record.get("outcome"),
                "provider": record.get("provider"),
                "build": OBJECT_ACTION_BUILD,
            }
        resolution_id = str(record.get("resolution_id") or "").strip()
        if not resolution_id:
            return {"status": "NO_RESOLUTION", "attempt_id": wanted, "build": OBJECT_ACTION_BUILD}

        resolved = resolve_action_resolution(
            actor,
            resolution_id,
            outcome,
            provider,
            resolution_data=resolution_data,
        )
        if str(resolved.get("status") or "") != "RESOLVED":
            return {
                "status": resolved.get("status"),
                "attempt_id": wanted,
                "resolution_id": resolution_id,
                "resolution": resolved,
                "build": OBJECT_ACTION_BUILD,
            }

        record.update(
            {
                "status": "RESOLVED",
                "resolved": True,
                "outcome": resolved.get("outcome"),
                "provider": resolved.get("provider"),
                "resolved_at": datetime.now(timezone.utc).isoformat(),
                "resolution_data": _plain_dict(resolved.get("resolution_data")),
            }
        )
        consequence = emit_world_action(
            {
                "action_id": f"OBJECT_ACTION_RESOLVED:{wanted}",
                "action_type": "OBJECT_ACTION_RESOLVED",
                "actor_npc_id": record.get("actor_npc_id"),
                "actor_name": record.get("actor_name"),
                "object_action_id": record.get("object_action_id"),
                "attempt_id": wanted,
                "resolution_id": resolution_id,
                "outcome": resolved.get("outcome"),
                "provider": resolved.get("provider"),
                "recipient_ids": [record.get("actor_npc_id")] if record.get("actor_npc_id") else [],
                "site_dbref": record.get("site_dbref"),
                "site_room_id": record.get("site_room_id"),
                "site_name": record.get("site_name"),
                "object_dbref": record.get("object_dbref"),
                "object_id": record.get("object_id"),
                "object_name": record.get("object_name"),
            }
        )
        record["action_consequence"] = consequence
        history[index] = record
        _save_history(actor, history)
        return {
            **dict(record),
            "campaign_observation": _observe_campaign_object_action(actor, record),
        }

    return {"status": "ATTEMPT_NOT_FOUND", "attempt_id": wanted, "build": OBJECT_ACTION_BUILD}
