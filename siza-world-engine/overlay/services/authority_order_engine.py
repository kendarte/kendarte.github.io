from datetime import datetime, timezone

from services.faction_engine import membership_authority, membership_for
from services.world_event_engine import (
    collect_event_candidates,
    inspect_event_sites,
    refresh_world_event_rules,
    set_event_state,
)


AUTHORITY_ORDER_BUILD = "0.25.0-faction-rank-authority"


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
        return {}


def _goal_type(value):
    return str((value or {}).get("goal_type") or (value or {}).get("type") or "").upper()


def _order_rows():
    rows = []
    for site_row in inspect_event_sites():
        site = site_row.get("site")
        contexts = _plain_dict(getattr(site.db, "world_order_issue_context", {})) if site else {}
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
            context = _record(contexts.get(order_id))
            rows.append(
                {
                    "site": site,
                    "site_name": site_row.get("name"),
                    "site_room_id": site_row.get("room_id"),
                    "rule": rule,
                    "instance": instances.get(order_id) or {},
                    "issue_context": context,
                    "order_id": order_id,
                    "authority_id": rule.get("authority_id"),
                    "authority_name": rule.get("authority_name"),
                    "issuer_id": context.get("issuer_id") or rule.get("issuer_id"),
                    "issuer_name": context.get("issuer_name") or rule.get("issuer_name"),
                    "issuer_rank_id": context.get("issuer_rank_id"),
                    "issuer_authority": context.get("issuer_authority"),
                    "faction_id": rule.get("faction_id"),
                    "faction_ids": _plain_list(rule.get("faction_ids")),
                    "required_issuer_authority": int(rule.get("required_issuer_authority", 0) or 0),
                    "issuer_rank_ids": _plain_list(rule.get("issuer_rank_ids")),
                    "recipient_rank_ids": _plain_list(rule.get("recipient_rank_ids")),
                    "recipient_roles": _plain_list(rule.get("recipient_roles")),
                    "exclude_issuer": bool(rule.get("exclude_issuer", False)),
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
    """Return ORDER candidates enriched with authority/faction metadata."""
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
        item["issuer_id"] = item.get("issuer_id") or row.get("issuer_id")
        item["issuer_name"] = item.get("issuer_name") or row.get("issuer_name")
        item["issuer_rank_id"] = item.get("issuer_rank_id") or row.get("issuer_rank_id")
        item["issuer_authority"] = item.get("issuer_authority") if item.get("issuer_authority") is not None else row.get("issuer_authority")
        item["faction_id"] = row.get("faction_id")
        item["faction_ids"] = list(row.get("faction_ids") or [])
        item["required_issuer_authority"] = row.get("required_issuer_authority")
        item["recipient_rank_ids"] = list(row.get("recipient_rank_ids") or [])
        item["order_kind"] = row.get("order_kind") or "DIRECTIVE"
        output.append(item)
    return output


def _write_issue_context(site, order_id, context):
    contexts = _plain_dict(getattr(site.db, "world_order_issue_context", {}))
    contexts[str(order_id)] = dict(context or {})
    site.db.world_order_issue_context = contexts


def check_order_authority(order_id, issuer):
    """Validate whether this NPC may issue one authored faction ORDER."""
    row = _row_for_order(order_id)
    if not row:
        return {"allowed": False, "reason": "ORDER_NOT_FOUND", "order_id": str(order_id or "")}
    if not issuer:
        return {"allowed": False, "reason": "NO_ISSUER", "order_id": row.get("order_id")}

    faction_id = str(row.get("faction_id") or "").strip()
    if not faction_id:
        return {
            "allowed": False,
            "reason": "ORDER_HAS_NO_FACTION_AUTHORITY",
            "order_id": row.get("order_id"),
        }

    membership = membership_for(issuer, faction_id, active_only=True)
    if not membership:
        return {
            "allowed": False,
            "reason": "ISSUER_NOT_ACTIVE_MEMBER",
            "order_id": row.get("order_id"),
            "faction_id": faction_id,
            "issuer": issuer.key,
        }

    issuer_rank_id = str(membership.get("rank_id") or membership.get("rank") or "").strip()
    allowed_ranks = {str(value) for value in row.get("issuer_rank_ids") or [] if value}
    if allowed_ranks and issuer_rank_id not in allowed_ranks:
        return {
            "allowed": False,
            "reason": "ISSUER_RANK_NOT_ALLOWED",
            "order_id": row.get("order_id"),
            "faction_id": faction_id,
            "issuer": issuer.key,
            "issuer_rank_id": issuer_rank_id,
        }

    authority = membership_authority(issuer, faction_id, active_only=True)
    authority = int(authority or 0)
    required = int(row.get("required_issuer_authority", 0) or 0)
    if authority < required:
        return {
            "allowed": False,
            "reason": "ISSUER_AUTHORITY_LOW",
            "order_id": row.get("order_id"),
            "faction_id": faction_id,
            "issuer": issuer.key,
            "issuer_rank_id": issuer_rank_id,
            "issuer_authority": authority,
            "required_issuer_authority": required,
        }

    return {
        "allowed": True,
        "reason": "AUTHORIZED",
        "order_id": row.get("order_id"),
        "faction_id": faction_id,
        "issuer": issuer.key,
        "issuer_id": str(getattr(issuer.db, "npc_id", "") or ""),
        "issuer_rank_id": issuer_rank_id,
        "issuer_authority": authority,
        "required_issuer_authority": required,
    }


def issue_order(order_id, issuer):
    """Issue one persistent ORDER only after faction/rank authority validation."""
    check = check_order_authority(order_id, issuer)
    if not check.get("allowed"):
        return check

    row = _row_for_order(order_id)
    site = row.get("site")
    rule = row.get("rule") or {}
    field = str(rule.get("field") or "").strip()
    if not site or not field:
        return {**check, "allowed": False, "reason": "ORDER_HAS_NO_PRODUCER"}

    context = {
        "issuer_id": check.get("issuer_id"),
        "issuer_name": issuer.key,
        "issuer_faction_id": check.get("faction_id"),
        "issuer_rank_id": check.get("issuer_rank_id"),
        "issuer_authority": check.get("issuer_authority"),
        "required_issuer_authority": check.get("required_issuer_authority"),
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_issue_context(site, order_id, context)

    value = rule.get("activate_value", rule.get("value", 1))
    state = set_event_state(site, field, value)
    results = refresh_world_event_rules()
    packet = next(
        (item for item in results if str(item.get("event_id") or "") == str(order_id)),
        None,
    )
    return {
        **check,
        "active_requested": True,
        "site": site,
        "field": field,
        "value": state.get(field) if state else value,
        "producer": packet,
        "issue_context": context,
    }


def set_order_active(order_id, active):
    """Admin/debug bypass: toggle an authored ORDER without authority validation."""
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
        "faction_id": row.get("faction_id"),
        "debug_bypass": True,
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
                "issuer_id": instance.get("issuer_id") or row.get("issuer_id"),
                "issuer_name": instance.get("issuer_name") or row.get("issuer_name"),
                "issuer_rank_id": instance.get("issuer_rank_id") or row.get("issuer_rank_id"),
                "issuer_authority": instance.get("issuer_authority") if instance.get("issuer_authority") is not None else row.get("issuer_authority"),
            }
        )
    return output
