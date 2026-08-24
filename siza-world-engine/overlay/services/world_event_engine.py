from datetime import datetime, timezone

from evennia import search_object, search_tag

from services.consequence_engine import emit_world_action
from services.faction_engine import has_active_membership
from services.perception_engine import (
    EVENT_AWARENESS_AUDIENCE,
    event_awareness_matches,
    normalize_event_awareness_mode,
    snapshot_event_awareness,
)


WORLD_EVENT_BUILD = "0.36.0-event-acknowledgement-actions"
EVENT_SITE_TAG = "siza_event_site"
EVENT_SITE_CATEGORY = "siza_world_event"
ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
EVENT_HISTORY_LIMIT = 200


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _plain_dict(value):
    try:
        return dict(value or {})
    except Exception:
        return {}


def _record(value):
    try:
        return {str(key): item for key, item in value.items()}
    except Exception:
        return None


def _coerce_number(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    try:
        text = str(value).strip()
        if "." in text:
            return float(text)
        return int(text)
    except Exception:
        return value


def _compare(actual, operator, expected):
    actual = _coerce_number(actual)
    expected = _coerce_number(expected)
    op = str(operator or "eq").lower()
    try:
        if op in {"lt", "<"}:
            return actual < expected
        if op in {"lte", "<=", "le"}:
            return actual <= expected
        if op in {"gt", ">"}:
            return actual > expected
        if op in {"gte", ">=", "ge"}:
            return actual >= expected
        if op in {"ne", "!=", "neq"}:
            return actual != expected
        return actual == expected
    except TypeError:
        return False


def event_sites():
    return list(search_tag(EVENT_SITE_TAG, category=EVENT_SITE_CATEGORY))


def _instances(site):
    output = []
    for raw in _plain_list(site.db.world_event_instances):
        item = _record(raw)
        if item is not None:
            output.append(item)
    return output


def _rules(site):
    output = []
    for raw in _plain_list(site.db.world_event_rules):
        item = _record(raw)
        if item is not None:
            output.append(item)
    return output


def _history(site):
    output = []
    for raw in _plain_list(getattr(site.db, "world_event_history", [])):
        item = _record(raw)
        if item is not None:
            output.append(item)
    return output


def _archive_event_occurrence(site, event, archived_at=None):
    """Persist one completed EVENT occurrence without changing the live instance schema."""
    if not site or not event or _event_goal_type(event) != "EVENT":
        return None
    event_id = str(event.get("id") or "").strip()
    occurrence = int(event.get("occurrence", 0) or 0)
    if not event_id or occurrence <= 0:
        return None

    now = archived_at or datetime.now(timezone.utc).isoformat()
    snapshot = dict(event)
    snapshot["active"] = False
    snapshot["status"] = "historical"
    snapshot["archived_at"] = now
    snapshot.setdefault("deactivated_at", now)

    history = _history(site)
    replaced = False
    for index, existing in enumerate(history):
        if (
            str(existing.get("id") or "") == event_id
            and int(existing.get("occurrence", 0) or 0) == occurrence
        ):
            history[index] = snapshot
            replaced = True
            break
    if not replaced:
        history.append(snapshot)

    if len(history) > EVENT_HISTORY_LIMIT:
        history = history[-EVENT_HISTORY_LIMIT:]
    site.db.world_event_history = history
    return snapshot


def _find_room(room_key, room_id=None):
    if not room_key:
        return None
    for obj in search_object(room_key):
        if room_id is None or obj.db.room_id == room_id:
            return obj
    return None


def _all_npcs():
    return [
        obj
        for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY)
        if bool(getattr(obj.db, "is_npc", False))
    ]


def _npc_job_id(npc):
    try:
        job = dict(npc.db.job or {})
    except Exception:
        job = {}
    return str(job.get("id") or "").strip()


def _event_goal_type(event):
    return str((event or {}).get("goal_type") or (event or {}).get("type") or "EVENT").upper()


def _default_priority(goal_type, event_default=80):
    goal_type = str(goal_type or "EVENT").upper()
    if goal_type == "DANGER":
        return 100
    if goal_type == "ORDER":
        return 60
    return int(event_default)


def _default_activity(goal_type):
    goal_type = str(goal_type or "EVENT").upper()
    if goal_type == "DANGER":
        return "evacuando un peligro del mundo"
    if goal_type == "ORDER":
        return "cumpliendo una orden de autoridad"
    return "atendiendo un evento del mundo"


def _affected_room_ids(site, event):
    values = {
        str(value)
        for value in _plain_list((event or {}).get("affected_room_ids"))
        if value
    }
    if not values and _event_goal_type(event) == "DANGER":
        room_id = str(getattr(site.db, "room_id", "") or "")
        if room_id:
            values.add(room_id)
    return values


def _audience_matches(npc, event):
    if not npc:
        return False
    npc_id = str(getattr(npc.db, "npc_id", "") or "")
    if not npc_id:
        return False

    npc_ids = {str(value) for value in _plain_list(event.get("npc_ids")) if value}
    if npc_ids and npc_id not in npc_ids:
        return False

    job_ids = {str(value) for value in _plain_list(event.get("job_ids")) if value}
    if job_ids and _npc_job_id(npc) not in job_ids:
        return False

    faction_ids = {str(value) for value in _plain_list(event.get("faction_ids")) if value}
    if faction_ids and not any(has_active_membership(npc, faction_id) for faction_id in faction_ids):
        return False

    return True


def _snapshot_event_awareness(site, event):
    """Freeze perception only for normal EVENT occurrences. ORDER/DANGER keep their own semantics."""
    if _event_goal_type(event) != "EVENT":
        return []
    mode = normalize_event_awareness_mode(event.get("awareness_mode"))
    if mode == EVENT_AWARENESS_AUDIENCE:
        return []
    eligible = [npc for npc in _all_npcs() if _audience_matches(npc, event)]
    return snapshot_event_awareness(eligible, site, mode=mode)


def _event_is_known_to(npc, event):
    if _event_goal_type(event) != "EVENT":
        return True
    return event_awareness_matches(npc, event)


def refresh_world_event_rules():
    """Evaluate persistent world state and activate/deactivate EVENT/DANGER/ORDER instances."""
    results = []
    now = datetime.now(timezone.utc).isoformat()

    for site in event_sites():
        state = _plain_dict(site.db.world_event_state)
        rules = _rules(site)
        instances = _instances(site)
        by_id = {
            str(item.get("id")): (index, item)
            for index, item in enumerate(instances)
            if item.get("id")
        }
        changed = False

        for rule in rules:
            if not bool(rule.get("enabled", True)):
                continue
            rule_id = str(rule.get("id") or "").strip()
            event_id = str(rule.get("event_id") or rule_id).strip()
            field = str(rule.get("field") or "").strip()
            if not rule_id or not event_id or not field:
                continue

            goal_type = str(rule.get("goal_type") or "EVENT").upper()
            default_priority = _default_priority(goal_type)
            response_mode = str(
                rule.get("response_mode")
                or ("PERSISTENT" if goal_type == "DANGER" else "ACK")
            ).upper()
            awareness_mode = normalize_event_awareness_mode(rule.get("awareness_mode"))

            actual = state.get(field)
            condition_met = _compare(actual, rule.get("op"), rule.get("value"))
            pair = by_id.get(event_id)
            if pair:
                index, event = pair
            else:
                index = len(instances)
                event = {
                    "id": event_id,
                    "active": False,
                    "status": "inactive",
                    "occurrence": 0,
                    "acknowledged_by": [],
                }
                instances.append(event)
                by_id[event_id] = (index, event)
                changed = True

            was_active = bool(event.get("active", False))
            event.update(
                {
                    "id": event_id,
                    "rule_id": rule_id,
                    "type": goal_type,
                    "goal_type": goal_type,
                    "response_mode": response_mode,
                    "priority": int(rule.get("priority", default_priority) or default_priority),
                    "target_room_id": rule.get("target_room_id")
                    or getattr(site.db, "room_id", None),
                    "target_room_key": rule.get("target_room_key") or site.key,
                    "activity": rule.get("activity") or _default_activity(goal_type),
                    "affected_room_ids": _plain_list(rule.get("affected_room_ids")),
                    "blocks_jobs": bool(rule.get("blocks_jobs", goal_type == "DANGER")),
                    "npc_ids": _plain_list(rule.get("npc_ids")),
                    "job_ids": _plain_list(rule.get("job_ids")),
                    "faction_ids": _plain_list(rule.get("faction_ids")),
                    "faction_id": rule.get("faction_id"),
                    "authority_id": rule.get("authority_id"),
                    "authority_name": rule.get("authority_name"),
                    "issuer_id": rule.get("issuer_id"),
                    "issuer_name": rule.get("issuer_name"),
                    "order_kind": rule.get("order_kind"),
                    "awareness_mode": awareness_mode,
                    "canon_status": rule.get("canon_status") or "prototype",
                }
            )

            if condition_met:
                event["active"] = True
                event["status"] = "active"
                if not was_active:
                    event["occurrence"] = int(event.get("occurrence", 0) or 0) + 1
                    event["activated_at"] = now
                    event["acknowledged_by"] = []
                    event.pop("last_ack_npc_id", None)
                    event.pop("last_ack_npc_name", None)
                    event.pop("last_ack_at", None)
                    if goal_type == "EVENT":
                        event["aware_npc_ids"] = _snapshot_event_awareness(site, event)
                    else:
                        event.pop("aware_npc_ids", None)
                    changed = True
            else:
                if was_active or event.get("status") != "inactive":
                    event["active"] = False
                    event["status"] = "inactive"
                    event["deactivated_at"] = now
                    if goal_type == "EVENT" and was_active:
                        _archive_event_occurrence(site, event, archived_at=now)
                    changed = True

            instances[index] = event
            results.append(
                {
                    "status": "OK",
                    "site": site.key,
                    "room_id": getattr(site.db, "room_id", None),
                    "rule_id": rule_id,
                    "event_id": event_id,
                    "goal_type": goal_type,
                    "field": field,
                    "actual": actual,
                    "condition_met": condition_met,
                    "event_active": bool(event.get("active")),
                    "event_status": event.get("status"),
                    "occurrence": event.get("occurrence"),
                    "authority_id": event.get("authority_id"),
                    "authority_name": event.get("authority_name"),
                    "faction_id": event.get("faction_id"),
                    "awareness_mode": event.get("awareness_mode"),
                    "aware_npc_ids": _plain_list(event.get("aware_npc_ids")),
                    "build": WORLD_EVENT_BUILD,
                }
            )

        if changed:
            site.db.world_event_instances = instances

    return results


def collect_event_candidates(npc, default_priority=80):
    """Return active persistent EVENT/DANGER/ORDER goals relevant and known to this NPC."""
    if not npc or not bool(npc.db.decision_enabled):
        return []

    npc_id = str(getattr(npc.db, "npc_id", "") or "")
    current_room_id = (
        str(getattr(getattr(npc, "location", None).db, "room_id", "") or "")
        if npc.location
        else ""
    )
    current_goal = _plain_dict(getattr(npc.db, "current_goal", {}))
    output = []

    for site in event_sites():
        for event in _instances(site):
            if not bool(event.get("active", False)):
                continue
            if not _audience_matches(npc, event):
                continue

            goal_type = _event_goal_type(event)
            if goal_type == "EVENT" and not _event_is_known_to(npc, event):
                continue

            if goal_type == "DANGER":
                target_room_id = str(event.get("target_room_id") or "")
                affected = _affected_room_ids(site, event)
                in_affected_room = bool(current_room_id and current_room_id in affected)
                continuing_escape = (
                    str(current_goal.get("source") or "") == "WORLD_EVENT"
                    and str(current_goal.get("event_id") or "")
                    == str(event.get("id") or "")
                    and current_room_id != target_room_id
                )
                if not in_affected_room and not continuing_escape:
                    continue
            else:
                acknowledged = {
                    str(value)
                    for value in _plain_list(event.get("acknowledged_by"))
                }
                if npc_id in acknowledged:
                    continue

            fallback_priority = _default_priority(goal_type, event_default=default_priority)
            try:
                priority = int(event.get("priority", fallback_priority))
            except (TypeError, ValueError):
                priority = int(fallback_priority)

            output.append(
                {
                    "id": f"{goal_type}:{event.get('id')}",
                    "event_id": event.get("id"),
                    "order_id": event.get("id") if goal_type == "ORDER" else None,
                    "type": goal_type,
                    "priority": priority,
                    "active": True,
                    "target_room_id": event.get("target_room_id"),
                    "target_room_key": event.get("target_room_key"),
                    "activity": event.get("activity") or _default_activity(goal_type),
                    "one_shot": False,
                    "source": "WORLD_EVENT",
                    "occurrence": event.get("occurrence"),
                    "event_site": site.key,
                    "response_mode": event.get("response_mode"),
                    "affected_room_ids": list(_affected_room_ids(site, event)),
                    "blocks_jobs": bool(event.get("blocks_jobs", False)),
                    "faction_ids": _plain_list(event.get("faction_ids")),
                    "faction_id": event.get("faction_id"),
                    "authority_id": event.get("authority_id"),
                    "authority_name": event.get("authority_name"),
                    "issuer_id": event.get("issuer_id"),
                    "issuer_name": event.get("issuer_name"),
                    "order_kind": event.get("order_kind"),
                    "awareness_mode": event.get("awareness_mode"),
                    "aware_npc_ids": _plain_list(event.get("aware_npc_ids")),
                }
            )
    return output


def acknowledge_world_event(npc, event_id):
    """Resolve one world incident response and emit a structured acknowledgement action."""
    wanted = str(event_id or "").strip()
    npc_id = str(getattr(npc.db, "npc_id", "") or "") if npc else ""
    if not wanted or not npc or not npc_id:
        return {"completed": False, "acknowledged": False, "reason": "BAD_INPUT"}

    for site in event_sites():
        instances = _instances(site)
        changed = False
        for index, event in enumerate(instances):
            if str(event.get("id") or "") != wanted:
                continue
            if not bool(event.get("active", False)):
                return {
                    "completed": False,
                    "acknowledged": False,
                    "reason": "EVENT_INACTIVE",
                    "event_id": wanted,
                    "goal_type": _event_goal_type(event),
                    "site": site,
                }
            if not _audience_matches(npc, event):
                return {
                    "completed": False,
                    "acknowledged": False,
                    "reason": "NOT_AUDIENCE",
                    "event_id": wanted,
                    "goal_type": _event_goal_type(event),
                    "site": site,
                }

            goal_type = _event_goal_type(event)
            if goal_type == "EVENT" and not _event_is_known_to(npc, event):
                return {
                    "completed": False,
                    "acknowledged": False,
                    "reason": "NOT_AWARE",
                    "event_id": wanted,
                    "goal_type": goal_type,
                    "event_occurrence": event.get("occurrence"),
                    "event_site": site.key,
                    "site": site,
                }

            if goal_type == "DANGER":
                target_room_id = str(event.get("target_room_id") or "")
                current_room_id = (
                    str(
                        getattr(
                            getattr(npc, "location", None).db,
                            "room_id",
                            "",
                        )
                        or ""
                    )
                    if npc.location
                    else ""
                )
                if target_room_id and current_room_id != target_room_id:
                    return {
                        "completed": False,
                        "acknowledged": False,
                        "reason": "DANGER_NOT_CLEAR",
                        "event_id": wanted,
                        "goal_type": goal_type,
                        "event_occurrence": event.get("occurrence"),
                        "event_site": site.key,
                        "site": site,
                    }
                return {
                    "completed": True,
                    "acknowledged": False,
                    "reason": "DANGER_ESCAPED",
                    "event_id": wanted,
                    "goal_type": goal_type,
                    "event_occurrence": event.get("occurrence"),
                    "event_site": site.key,
                    "site": site,
                }

            acknowledged = [
                str(value) for value in _plain_list(event.get("acknowledged_by"))
            ]
            already = npc_id in acknowledged
            action_consequence = None
            if not already:
                acknowledged.append(npc_id)
                event["acknowledged_by"] = acknowledged
                event["last_ack_npc_id"] = npc_id
                event["last_ack_npc_name"] = npc.key
                event["last_ack_at"] = datetime.now(timezone.utc).isoformat()
                instances[index] = event
                changed = True
            if changed:
                site.db.world_event_instances = instances

            if goal_type == "EVENT" and not already:
                occurrence = int(event.get("occurrence", 0) or 0)
                action_consequence = emit_world_action(
                    {
                        "action_id": f"EVENT_ACKNOWLEDGED:{wanted}:{occurrence}:{npc_id}",
                        "action_type": "EVENT_ACKNOWLEDGED",
                        "actor_npc_id": npc_id,
                        "actor_name": npc.key,
                        "event_id": wanted,
                        "occurrence": occurrence,
                        "event_site": site.key,
                        "event_room_id": getattr(site.db, "room_id", None),
                        "target_room_id": event.get("target_room_id"),
                        "target_room_key": event.get("target_room_key"),
                        "recipient_ids": [npc_id],
                    }
                )

            if goal_type == "ORDER":
                reason = "ORDER_ALREADY_COMPLETED" if already else "ORDER_COMPLETED"
            else:
                reason = "ALREADY_ACKNOWLEDGED" if already else "ACKNOWLEDGED"

            return {
                "completed": True,
                "acknowledged": not already,
                "reason": reason,
                "event_id": wanted,
                "goal_type": goal_type,
                "event_occurrence": event.get("occurrence"),
                "event_site": site.key,
                "authority_id": event.get("authority_id"),
                "authority_name": event.get("authority_name"),
                "faction_id": event.get("faction_id"),
                "issuer_id": event.get("issuer_id"),
                "issuer_name": event.get("issuer_name"),
                "awareness_mode": event.get("awareness_mode"),
                "action_consequence": action_consequence,
                "site": site,
            }

    return {
        "completed": False,
        "acknowledged": False,
        "reason": "EVENT_NOT_FOUND",
        "event_id": wanted,
    }


def danger_blocks_room(room, npc=None):
    """Return highest-priority active DANGER that blocks work in this room."""
    if not room:
        return None
    room_id = str(getattr(room.db, "room_id", "") or "")
    if not room_id:
        return None

    blockers = []
    for site in event_sites():
        for event in _instances(site):
            if not bool(event.get("active", False)):
                continue
            if _event_goal_type(event) != "DANGER":
                continue
            if not bool(event.get("blocks_jobs", True)):
                continue
            if npc is not None and not _audience_matches(npc, event):
                continue
            if room_id not in _affected_room_ids(site, event):
                continue
            try:
                priority = int(event.get("priority", 100))
            except (TypeError, ValueError):
                priority = 100
            blockers.append(
                {
                    "event_id": event.get("id"),
                    "type": "DANGER",
                    "priority": priority,
                    "site": site.key,
                    "room_id": room_id,
                    "occurrence": event.get("occurrence"),
                }
            )

    blockers.sort(key=lambda item: int(item.get("priority", 0)), reverse=True)
    return blockers[0] if blockers else None


def set_event_state(site, field, value):
    if not site or not field:
        return None
    state = _plain_dict(site.db.world_event_state)
    state[str(field)] = _coerce_number(value)
    site.db.world_event_state = state
    return state


def inspect_event_sites():
    rows = []
    for site in event_sites():
        rows.append(
            {
                "site": site,
                "name": site.key,
                "room_id": getattr(site.db, "room_id", None),
                "state": _plain_dict(site.db.world_event_state),
                "rules": _rules(site),
                "instances": _instances(site),
                "history": _history(site),
            }
        )
    return rows
