ACTION_RESOLUTION_BUILD = "0.38.0-adventure-stats-check-contract"

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


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def normalize_stat_key(value):
    key = str(value or "").strip().upper()
    return STAT_ALIASES.get(key)


def normalize_check_mode(value):
    mode = str(value or "").strip().upper()
    return mode if mode in CHECK_MODES else None


def normalize_check_trigger(value):
    trigger = str(value or "").strip().upper()
    return trigger if trigger in CHECK_TRIGGERS else None


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
    """Build an authoritative check packet. No outcome is resolved until mode formulas are authored."""
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
