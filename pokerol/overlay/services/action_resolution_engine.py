from datetime import datetime, timezone
from uuid import uuid4


ACTION_RESOLUTION_BUILD = "0.39.0-action-resolution-lifecycle"
RESOLUTION_HISTORY_LIMIT = 50

ADVENTURE_STATS = (
    "FUE",
    "AGI",
    "COO",
    "INT",
    "PER",
    "PSI",
)

STAT_ALIASES = {
    "FUE": "FUE",
    "FUERZA": "FUE",
    "AGI": "AGI",
    "AGILIDAD": "AGI",
    "COO": "COO",
    "COORDINACION": "COO",
    "COORDINACIÓN": "COO",
    "INT": "INT",
    "INTELIGENCIA": "INT",
    "PER": "PER",
    "PERCEPCION": "PER",
    "PERCEPCIÓN": "PER",
    "PSI": "PSI",
    "PSIQUE": "PSI",
}

CHECK_MODES = (
    "DIRECT",
    "ACCUMULATE",
    "CONFRONT",
    "SYNCHRONIZE",
)

CHECK_TRIGGERS = (
    "OBSTACLE",
    "OPPOSITION",
    "SYNCHRONY",
)

MODE_OUTCOMES = {
    "DIRECT": ("SUCCESS", "FAILURE"),
    "ACCUMULATE": ("PROGRESS", "SETBACK", "COMPLETE", "FAILURE"),
    "CONFRONT": ("ACTOR_WIN", "TARGET_WIN", "TIE"),
    "SYNCHRONIZE": ("SYNC", "MISS"),
}


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


def normalize_stat_key(value):
    key = str(value or "").strip().upper()
    return STAT_ALIASES.get(key)


def normalize_check_mode(value):
    mode = str(value or "").strip().upper()
    return mode if mode in CHECK_MODES else None


def normalize_check_trigger(value):
    trigger = str(value or "").strip().upper()
    return trigger if trigger in CHECK_TRIGGERS else None


def allowed_outcomes(mode):
    return tuple(MODE_OUTCOMES.get(normalize_check_mode(mode), ()))


def adventure_stats(npc):
    """Return only explicitly authored persistent Adventure stats; missing is not treated as zero."""
    if not npc:
        return {}
    raw = _plain_dict(getattr(npc.db, "adventure_stats", {}))
    output = {}
    for key, value in raw.items():
        stat = normalize_stat_key(key)
        if not stat:
            continue
        try:
            output[stat] = int(value)
        except (TypeError, ValueError):
            continue
    return output


def stat_value(npc, stat_key):
    stat = normalize_stat_key(stat_key)
    if not stat:
        return None
    return adventure_stats(npc).get(stat)


def set_adventure_stat(npc, stat_key, value):
    if not npc:
        return {"success": False, "reason": "NO_NPC"}
    stat = normalize_stat_key(stat_key)
    if not stat:
        return {"success": False, "reason": "BAD_STAT"}
    try:
        value = int(value)
    except (TypeError, ValueError):
        return {"success": False, "reason": "BAD_VALUE", "stat": stat}

    stats = adventure_stats(npc)
    before = stats.get(stat)
    stats[stat] = value
    npc.db.adventure_stats = stats
    return {
        "success": True,
        "reason": "SET",
        "npc": npc.key,
        "npc_id": str(getattr(npc.db, "npc_id", "") or ""),
        "stat": stat,
        "before": before,
        "after": value,
    }


def inspect_adventure_stats(npc):
    values = adventure_stats(npc)
    return {
        "build": ACTION_RESOLUTION_BUILD,
        "npc": npc.key if npc else None,
        "npc_id": str(getattr(npc.db, "npc_id", "") or "") if npc else None,
        "stats": {key: values.get(key) for key in ADVENTURE_STATS},
        "authored_count": len(values),
    }


def normalize_check_spec(spec):
    """Validate authored check metadata without inventing a dice formula."""
    raw = _plain_dict(spec)
    trigger = normalize_check_trigger(raw.get("trigger"))
    mode = normalize_check_mode(raw.get("mode"))
    stat = normalize_stat_key(raw.get("stat"))
    target_stat = normalize_stat_key(raw.get("target_stat")) if raw.get("target_stat") else None

    errors = []
    if not trigger:
        errors.append("BAD_TRIGGER")
    if not mode:
        errors.append("BAD_MODE")
    if not stat:
        errors.append("BAD_STAT")
    if raw.get("target_stat") and not target_stat:
        errors.append("BAD_TARGET_STAT")

    return {
        "valid": not errors,
        "errors": errors,
        "id": str(raw.get("id") or "").strip() or None,
        "trigger": trigger,
        "mode": mode,
        "stat": stat,
        "target_stat": target_stat,
        "difficulty": raw.get("difficulty"),
        "metadata": _plain_dict(raw.get("metadata")),
    }


def action_requires_resolution(action_spec):
    """Routine/cotidian actions do not roll. A check must be explicitly authored with a valid trigger."""
    raw = _plain_dict(action_spec)
    check = raw.get("check")
    if not check:
        return False
    normalized = normalize_check_spec(check)
    return bool(normalized.get("valid") and normalized.get("trigger") in CHECK_TRIGGERS)


def prepare_action_check(actor, check_spec, target=None):
    """Build an authoritative check packet. No outcome is resolved until a math/provider layer supplies one."""
    check = normalize_check_spec(check_spec)
    if not check.get("valid"):
        return {
            "status": "INVALID_CHECK",
            "build": ACTION_RESOLUTION_BUILD,
            "check": check,
        }

    actor_value = stat_value(actor, check.get("stat"))
    if actor_value is None:
        return {
            "status": "MISSING_ACTOR_STAT",
            "build": ACTION_RESOLUTION_BUILD,
            "check": check,
            "actor": actor.key if actor else None,
            "actor_stat": check.get("stat"),
        }

    target_value = None
    if check.get("target_stat"):
        if target is None:
            return {
                "status": "MISSING_TARGET",
                "build": ACTION_RESOLUTION_BUILD,
                "check": check,
                "actor": actor.key if actor else None,
                "actor_stat_value": actor_value,
            }
        target_value = stat_value(target, check.get("target_stat"))
        if target_value is None:
            return {
                "status": "MISSING_TARGET_STAT",
                "build": ACTION_RESOLUTION_BUILD,
                "check": check,
                "actor": actor.key if actor else None,
                "actor_stat_value": actor_value,
                "target": target.key,
                "target_stat": check.get("target_stat"),
            }

    return {
        "status": "READY_UNRESOLVED",
        "build": ACTION_RESOLUTION_BUILD,
        "check": check,
        "actor": actor.key if actor else None,
        "actor_npc_id": str(getattr(actor.db, "npc_id", "") or "") if actor else None,
        "actor_stat": check.get("stat"),
        "actor_stat_value": actor_value,
        "target": target.key if target else None,
        "target_npc_id": str(getattr(target.db, "npc_id", "") or "") if target else None,
        "target_stat": check.get("target_stat"),
        "target_stat_value": target_value,
        "resolved": False,
        "outcome": None,
        "reason": "FORMULA_NOT_AUTHORED",
    }


def action_resolution_history(actor):
    output = []
    if not actor:
        return output
    for raw in _plain_list(getattr(actor.db, "action_resolution_history", [])):
        item = _plain_dict(raw)
        if item.get("resolution_id"):
            output.append(item)
    return output


def _save_history(actor, history):
    actor.db.action_resolution_history = list(history)[-RESOLUTION_HISTORY_LIMIT:]


def begin_action_resolution(actor, check_spec, target=None, resolution_id=None):
    """Persist a prepared check as PENDING_RESOLUTION without selecting any dice/math policy."""
    prepared = prepare_action_check(actor, check_spec, target=target)
    if prepared.get("status") != "READY_UNRESOLVED":
        packet = dict(prepared)
        packet["resolution_status"] = "BLOCKED"
        return packet

    check = dict(prepared.get("check") or {})
    rid = str(resolution_id or "").strip() or f"RES-{uuid4().hex}"
    history = action_resolution_history(actor)
    if any(str(row.get("resolution_id")) == rid for row in history):
        return {
            "status": "DUPLICATE_RESOLUTION_ID",
            "resolution_id": rid,
            "build": ACTION_RESOLUTION_BUILD,
        }

    record = {
        "resolution_id": rid,
        "check_id": check.get("id"),
        "status": "PENDING_RESOLUTION",
        "resolved": False,
        "outcome": None,
        "provider": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "actor_npc_id": prepared.get("actor_npc_id"),
        "actor_name": prepared.get("actor"),
        "actor_stat": prepared.get("actor_stat"),
        "actor_stat_value": prepared.get("actor_stat_value"),
        "target_npc_id": prepared.get("target_npc_id"),
        "target_name": prepared.get("target"),
        "target_stat": prepared.get("target_stat"),
        "target_stat_value": prepared.get("target_stat_value"),
        "trigger": check.get("trigger"),
        "mode": check.get("mode"),
        "difficulty": check.get("difficulty"),
        "metadata": _plain_dict(check.get("metadata")),
        "allowed_outcomes": list(allowed_outcomes(check.get("mode"))),
        "resolution_data": {},
        "build": ACTION_RESOLUTION_BUILD,
    }
    history.append(record)
    _save_history(actor, history)
    return dict(record)


def resolve_action_resolution(actor, resolution_id, outcome, provider, resolution_data=None):
    """Accept an outcome from an explicit provider; this layer validates and persists but does not calculate it."""
    if not actor:
        return {"status": "NO_ACTOR", "build": ACTION_RESOLUTION_BUILD}
    rid = str(resolution_id or "").strip()
    provider = str(provider or "").strip()
    wanted_outcome = str(outcome or "").strip().upper()
    if not rid:
        return {"status": "BAD_RESOLUTION_ID", "build": ACTION_RESOLUTION_BUILD}
    if not provider:
        return {"status": "MISSING_PROVIDER", "resolution_id": rid, "build": ACTION_RESOLUTION_BUILD}

    history = action_resolution_history(actor)
    for index, current in enumerate(history):
        if str(current.get("resolution_id")) != rid:
            continue
        record = dict(current)
        if bool(record.get("resolved")) or str(record.get("status")) == "RESOLVED":
            return {
                "status": "ALREADY_RESOLVED",
                "resolution_id": rid,
                "outcome": record.get("outcome"),
                "provider": record.get("provider"),
                "build": ACTION_RESOLUTION_BUILD,
            }

        allowed = set(allowed_outcomes(record.get("mode")))
        if wanted_outcome not in allowed:
            return {
                "status": "INVALID_OUTCOME",
                "resolution_id": rid,
                "mode": record.get("mode"),
                "outcome": wanted_outcome,
                "allowed_outcomes": sorted(allowed),
                "build": ACTION_RESOLUTION_BUILD,
            }

        record["status"] = "RESOLVED"
        record["resolved"] = True
        record["outcome"] = wanted_outcome
        record["provider"] = provider
        record["resolved_at"] = datetime.now(timezone.utc).isoformat()
        record["resolution_data"] = _plain_dict(resolution_data)
        history[index] = record
        _save_history(actor, history)
        return dict(record)

    return {
        "status": "RESOLUTION_NOT_FOUND",
        "resolution_id": rid,
        "build": ACTION_RESOLUTION_BUILD,
    }


def inspect_action_resolutions(actor):
    history = action_resolution_history(actor)
    return {
        "build": ACTION_RESOLUTION_BUILD,
        "actor": actor.key if actor else None,
        "actor_npc_id": str(getattr(actor.db, "npc_id", "") or "") if actor else None,
        "count": len(history),
        "records": history,
    }
