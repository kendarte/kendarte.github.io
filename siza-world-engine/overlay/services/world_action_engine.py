from datetime import datetime, timezone
from uuid import uuid4

from services.action_resolution_engine import (
    action_requires_resolution,
    begin_action_resolution,
    resolve_action_resolution,
)
from services.consequence_engine import emit_world_action


WORLD_ACTION_BUILD = "0.41.0-generic-action-pipeline"
WORLD_ACTION_HISTORY_LIMIT = 50


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


def authored_world_actions(site):
    """Return normalized authored actions declared on one room/object via db.world_actions."""
    output = []
    if not site:
        return output
    for raw in _plain_list(getattr(site.db, "world_actions", [])):
        item = _record(raw)
        if not item:
            continue
        action_id = str(item.get("id") or "").strip()
        if not action_id:
            continue
        item["id"] = action_id
        item["enabled"] = bool(item.get("enabled", True))
        item.setdefault("name", action_id)
        item.setdefault("activity", item.get("name") or action_id)
        item.setdefault("canon_status", "prototype")
        item["metadata"] = _plain_dict(item.get("metadata"))
        if item.get("check") is not None:
            item["check"] = _plain_dict(item.get("check"))
        output.append(item)
    return output


def available_world_actions(actor):
    """Actions are local by construction: only the actor's current location is queried."""
    if not actor or not getattr(actor, "location", None):
        return []
    return [item for item in authored_world_actions(actor.location) if bool(item.get("enabled", True))]


def find_world_action(actor, action_id):
    wanted = str(action_id or "").strip()
    if not wanted:
        return None
    for item in available_world_actions(actor):
        if str(item.get("id") or "") == wanted:
            return item
    return None


def world_action_history(actor):
    output = []
    if not actor:
        return output
    for raw in _plain_list(getattr(actor.db, "world_action_history", [])):
        item = _record(raw)
        if item and item.get("attempt_id"):
            output.append(item)
    return output


def _save_history(actor, history):
    actor.db.world_action_history = list(history)[-WORLD_ACTION_HISTORY_LIMIT:]


def _actor_npc_id(actor):
    return str(getattr(actor.db, "npc_id", "") or "").strip() if actor else ""


def _site_payload(actor):
    site = getattr(actor, "location", None)
    return {
        "site_name": site.key if site else None,
        "site_room_id": str(getattr(site.db, "room_id", "") or "") if site else None,
        "site_dbref": int(site.id) if site else None,
    }


def begin_world_action(actor, action_id, target=None, attempt_id=None):
    """Start one authored local action. Checked actions become pending; routine actions complete immediately."""
    if not actor:
        return {"status": "NO_ACTOR", "build": WORLD_ACTION_BUILD}
    if not getattr(actor, "location", None):
        return {"status": "NO_LOCATION", "build": WORLD_ACTION_BUILD}

    action = find_world_action(actor, action_id)
    if not action:
        return {
            "status": "ACTION_NOT_AVAILABLE",
            "world_action_id": str(action_id or "").strip(),
            "build": WORLD_ACTION_BUILD,
        }

    attempt_id = str(attempt_id or "").strip() or f"WACT-{uuid4().hex}"
    history = world_action_history(actor)
    if any(str(row.get("attempt_id") or "") == attempt_id for row in history):
        return {
            "status": "DUPLICATE_ATTEMPT_ID",
            "attempt_id": attempt_id,
            "build": WORLD_ACTION_BUILD,
        }

    now = datetime.now(timezone.utc).isoformat()
    record = {
        "attempt_id": attempt_id,
        "world_action_id": action.get("id"),
        "world_action_name": action.get("name"),
        "activity": action.get("activity"),
        "canon_status": action.get("canon_status") or "prototype",
        "actor_npc_id": _actor_npc_id(actor),
        "actor_name": actor.key,
        "created_at": now,
        "metadata": _plain_dict(action.get("metadata")),
        "build": WORLD_ACTION_BUILD,
        **_site_payload(actor),
    }

    if action_requires_resolution(action):
        resolution_id = f"{attempt_id}:RESOLUTION"
        resolution = begin_action_resolution(
            actor,
            action.get("check") or {},
            target=target,
            resolution_id=resolution_id,
        )
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
                "target_npc_id": resolution.get("target_npc_id"),
                "target_name": resolution.get("target_name"),
                "target_stat": resolution.get("target_stat"),
                "target_stat_value": resolution.get("target_stat_value"),
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
    history.append(record)
    _save_history(actor, history)
    consequence = emit_world_action(
        {
            "action_id": f"WORLD_ACTION_COMPLETED:{attempt_id}",
            "action_type": "WORLD_ACTION_COMPLETED",
            "actor_npc_id": _actor_npc_id(actor),
            "actor_name": actor.key,
            "world_action_id": action.get("id"),
            "attempt_id": attempt_id,
            "outcome": "COMPLETED",
            "site_room_id": record.get("site_room_id"),
            "site_name": record.get("site_name"),
            "recipient_ids": [_actor_npc_id(actor)] if _actor_npc_id(actor) else [],
        }
    )
    record["action_consequence"] = consequence
    history[-1] = record
    _save_history(actor, history)
    return dict(record)


def resolve_world_action(actor, attempt_id, outcome, provider, resolution_data=None):
    """Resolve one checked world action using the validated external-provider lifecycle from v0.39."""
    if not actor:
        return {"status": "NO_ACTOR", "build": WORLD_ACTION_BUILD}
    wanted = str(attempt_id or "").strip()
    history = world_action_history(actor)

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
                "build": WORLD_ACTION_BUILD,
            }
        resolution_id = str(record.get("resolution_id") or "").strip()
        if not resolution_id:
            return {
                "status": "NO_RESOLUTION",
                "attempt_id": wanted,
                "build": WORLD_ACTION_BUILD,
            }

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
                "build": WORLD_ACTION_BUILD,
            }

        now = datetime.now(timezone.utc).isoformat()
        record.update(
            {
                "status": "RESOLVED",
                "resolved": True,
                "outcome": resolved.get("outcome"),
                "provider": resolved.get("provider"),
                "resolved_at": now,
                "resolution_data": _plain_dict(resolved.get("resolution_data")),
            }
        )
        consequence = emit_world_action(
            {
                "action_id": f"WORLD_ACTION_RESOLVED:{wanted}",
                "action_type": "WORLD_ACTION_RESOLVED",
                "actor_npc_id": _actor_npc_id(actor),
                "actor_name": actor.key,
                "world_action_id": record.get("world_action_id"),
                "attempt_id": wanted,
                "resolution_id": resolution_id,
                "outcome": resolved.get("outcome"),
                "provider": resolved.get("provider"),
                "site_room_id": record.get("site_room_id"),
                "site_name": record.get("site_name"),
                "recipient_ids": [_actor_npc_id(actor)] if _actor_npc_id(actor) else [],
            }
        )
        record["action_consequence"] = consequence
        history[index] = record
        _save_history(actor, history)
        return dict(record)

    return {
        "status": "ATTEMPT_NOT_FOUND",
        "attempt_id": wanted,
        "build": WORLD_ACTION_BUILD,
    }
