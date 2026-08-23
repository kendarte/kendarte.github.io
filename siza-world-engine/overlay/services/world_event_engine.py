from datetime import datetime, timezone

from evennia import search_object, search_tag


WORLD_EVENT_BUILD = "0.18.0-world-events"
EVENT_SITE_TAG = "siza_event_site"
EVENT_SITE_CATEGORY = "siza_world_event"


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


def _find_room(room_key, room_id=None):
    if not room_key:
        return None
    for obj in search_object(room_key):
        if room_id is None or obj.db.room_id == room_id:
            return obj
    return None


def _npc_job_id(npc):
    try:
        job = dict(npc.db.job or {})
    except Exception:
        job = {}
    return str(job.get("id") or "").strip()


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

    return True


def refresh_world_event_rules():
    """Evaluate persistent world state and activate/deactivate EVENT instances."""
    results = []
    now = datetime.now(timezone.utc).isoformat()

    for site in event_sites():
        state = _plain_dict(site.db.world_event_state)
        rules = _rules(site)
        instances = _instances(site)
        by_id = {str(item.get("id")): (index, item) for index, item in enumerate(instances) if item.get("id")}
        changed = False

        for rule in rules:
            if not bool(rule.get("enabled", True)):
                continue
            rule_id = str(rule.get("id") or "").strip()
            event_id = str(rule.get("event_id") or rule_id).strip()
            field = str(rule.get("field") or "").strip()
            if not rule_id or not event_id or not field:
                continue

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
                    "type": "EVENT",
                    "priority": int(rule.get("priority", 80) or 80),
                    "target_room_id": rule.get("target_room_id") or getattr(site.db, "room_id", None),
                    "target_room_key": rule.get("target_room_key") or site.key,
                    "activity": rule.get("activity") or "atendiendo un evento del mundo",
                    "npc_ids": _plain_list(rule.get("npc_ids")),
                    "job_ids": _plain_list(rule.get("job_ids")),
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
                    changed = True
            else:
                if was_active or event.get("status") != "inactive":
                    event["active"] = False
                    event["status"] = "inactive"
                    event["deactivated_at"] = now
                    changed = True

            instances[index] = event
            results.append(
                {
                    "status": "OK",
                    "site": site.key,
                    "room_id": getattr(site.db, "room_id", None),
                    "rule_id": rule_id,
                    "event_id": event_id,
                    "field": field,
                    "actual": actual,
                    "condition_met": condition_met,
                    "event_active": bool(event.get("active")),
                    "event_status": event.get("status"),
                    "occurrence": event.get("occurrence"),
                    "build": WORLD_EVENT_BUILD,
                }
            )

        if changed:
            site.db.world_event_instances = instances

    return results


def collect_event_candidates(npc, default_priority=80):
    """Return active persistent world EVENT goals relevant and unacknowledged by this NPC."""
    if not npc or not bool(npc.db.decision_enabled):
        return []
    npc_id = str(getattr(npc.db, "npc_id", "") or "")
    output = []

    for site in event_sites():
        for event in _instances(site):
            if not bool(event.get("active", False)):
                continue
            if not _audience_matches(npc, event):
                continue
            acknowledged = {str(value) for value in _plain_list(event.get("acknowledged_by"))}
            if npc_id in acknowledged:
                continue
            try:
                priority = int(event.get("priority", default_priority))
            except (TypeError, ValueError):
                priority = int(default_priority)
            output.append(
                {
                    "id": f"EVENT:{event.get('id')}",
                    "event_id": event.get("id"),
                    "type": "EVENT",
                    "priority": priority,
                    "active": True,
                    "target_room_id": event.get("target_room_id"),
                    "target_room_key": event.get("target_room_key"),
                    "activity": event.get("activity") or "atendiendo un evento del mundo",
                    "one_shot": False,
                    "source": "WORLD_EVENT",
                    "occurrence": event.get("occurrence"),
                    "event_site": site.key,
                }
            )
    return output


def acknowledge_world_event(npc, event_id):
    """Acknowledge one active EVENT for one NPC without changing the event's world condition."""
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
                    "site": site,
                }
            if not _audience_matches(npc, event):
                return {
                    "completed": False,
                    "acknowledged": False,
                    "reason": "NOT_AUDIENCE",
                    "event_id": wanted,
                    "site": site,
                }

            acknowledged = [str(value) for value in _plain_list(event.get("acknowledged_by"))]
            already = npc_id in acknowledged
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
            return {
                "completed": True,
                "acknowledged": not already,
                "reason": "ALREADY_ACKNOWLEDGED" if already else "ACKNOWLEDGED",
                "event_id": wanted,
                "event_occurrence": event.get("occurrence"),
                "event_site": site.key,
                "site": site,
            }

    return {"completed": False, "acknowledged": False, "reason": "EVENT_NOT_FOUND", "event_id": wanted}


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
            }
        )
    return rows
