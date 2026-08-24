from services.world_event_engine import (
    collect_event_candidates,
    inspect_event_sites,
    refresh_world_event_rules,
    set_event_state,
)


AUTHORITY_ORDER_BUILD = "0.23.0-authority-orders"


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _record(value):
    try:
        return {str(key): item for key, item in value.items()}
    except Exception:
        return {}


def _goal_type(value):
    return str((value or {}).get("goal_type") or (value or {}).get("type") or "").upper()


def _order_rows():
    rows = []
    for site_row in inspect_event_sites():
        site = site_row.get("site")
        instances = {
            str(item.get("id")): item
            for item in site_row.get("instances") or []
            if item.get("id")
        }
        for raw_rule in site_row.get("rules") or []:
            rule = _record(raw_rule)
            if _goal_type(rule) != "ORDER":
                continue
            order_id = str(rule.get("event_id") or rule.get("id") or "").strip()
            if not order_id:
                continue
            rows.append(
                {
                    "site": site,
                    "site_name": site_row.get("name"),
                    "site_room_id": site_row.get("room_id"),
                    "rule": rule,
                    "instance": instances.get(order_id) or {},
                    "order_id": order_id,
                    "authority_id": rule.get("authority_id"),
                    "authority_name": rule.get("authority_name"),
                    "issuer_id": rule.get("issuer_id"),
                    "issuer_name": rule.get("issuer_name"),
                    "order_kind": rule.get("order_kind") or "DIRECTIVE",
                    "target_room_id": rule.get("target_room_id"),
                    "target_room_key": rule.get("target_room_key"),
                    "npc_ids": _plain_list(rule.get("npc_ids")),
                    "job_ids": _plain_list(rule.get("job_ids")),
                    "priority": rule.get("priority"),
                    "canon_status": rule.get("canon_status") or "prototype",
                }
            )
    return rows


def _row_for_order(order_id):
    wanted = str(order_id or "").strip()
    for row in _order_rows():
        if str(row.get("order_id") or "") == wanted:
            return row
    return None


def collect_order_candidates(npc):
    """Return ORDER candidates enriched with authority metadata for diagnostics."""
    refresh_world_event_rules()
    meta = {str(row.get("order_id")): row for row in _order_rows()}
    output = []
    for raw in collect_event_candidates(npc):
        if _goal_type(raw) != "ORDER":
            continue
        item = dict(raw)
        row = meta.get(str(item.get("event_id") or "")) or {}
        item["order_id"] = item.get("event_id")
        item["authority_id"] = row.get("authority_id")
        item["authority_name"] = row.get("authority_name")
        item["issuer_id"] = row.get("issuer_id")
        item["issuer_name"] = row.get("issuer_name")
        item["order_kind"] = row.get("order_kind") or "DIRECTIVE"
        output.append(item)
    return output


def set_order_active(order_id, active):
    """Debug/admin toggle for an authored ORDER producer using explicit activation values."""
    row = _row_for_order(order_id)
    if not row:
        return None
    rule = row.get("rule") or {}
    site = row.get("site")
    field = str(rule.get("field") or "").strip()
    if not site or not field:
        return None

    desired = bool(active)
    if desired:
        value = rule.get("activate_value", rule.get("value", 1))
    else:
        value = rule.get("deactivate_value", 0)

    state = set_event_state(site, field, value)
    results = refresh_world_event_rules()
    packet = next(
        (
            item
            for item in results
            if str(item.get("event_id") or "") == str(order_id)
        ),
        None,
    )
    return {
        "order_id": str(order_id),
        "active_requested": desired,
        "site": site,
        "field": field,
        "value": state.get(field) if state else value,
        "producer": packet,
        "authority_id": row.get("authority_id"),
        "authority_name": row.get("authority_name"),
    }


def inspect_orders(npc=None):
    refresh_world_event_rules()
    if npc is not None:
        return collect_order_candidates(npc)

    output = []
    for row in _order_rows():
        instance = dict(row.get("instance") or {})
        rule = dict(row.get("rule") or {})
        output.append(
            {
                **row,
                "active": bool(instance.get("active", False)),
                "status": instance.get("status") or "inactive",
                "occurrence": int(instance.get("occurrence", 0) or 0),
                "completed_by": _plain_list(instance.get("acknowledged_by")),
                "priority": instance.get("priority", rule.get("priority")),
                "activity": instance.get("activity") or rule.get("activity"),
            }
        )
    return output
