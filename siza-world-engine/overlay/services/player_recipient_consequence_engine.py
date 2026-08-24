from services.consequence_engine import consequence_rules
from services.knowledge_context_engine import knowledge_levels, set_knowledge_level


PLAYER_RECIPIENT_BUILD = "0.56.0-player-actor-knowledge-consequences"
APPLIED_ACTIONS_ATTR = "player_consequence_action_ids"
APPLIED_ACTIONS_LIMIT = 100


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


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _normalize_compare(key, value):
    if key in {"action_type", "goal_type", "type", "source", "outcome"}:
        return str(value or "").upper()
    return str(value or "")


def _condition_matches(action, when):
    packet = dict(action or {})
    for key, expected in _plain_dict(when).items():
        actual = packet.get(key)
        if isinstance(expected, (list, tuple, set)):
            wanted = {_normalize_compare(key, item) for item in expected}
            if _normalize_compare(key, actual) not in wanted:
                return False
            continue
        if _normalize_compare(key, actual) != _normalize_compare(key, expected):
            return False
    return True


def _resolve_template(value, action):
    if isinstance(value, str) and value.startswith("$"):
        return (action or {}).get(value[1:])
    if hasattr(value, "items"):
        try:
            return {
                str(key): _resolve_template(item, action)
                for key, item in value.items()
            }
        except Exception:
            pass
    if isinstance(value, (list, tuple, set)):
        return [_resolve_template(item, action) for item in value]
    if not isinstance(value, (str, bytes)) and hasattr(value, "__iter__"):
        try:
            return [_resolve_template(item, action) for item in value]
        except Exception:
            pass
    return value


def _knowledge_result(actor, rule, action):
    spec = _plain_dict((rule or {}).get("knowledge"))
    if not spec:
        return None
    resolved = _plain_dict(_resolve_template(spec, action))
    key = str(resolved.get("knowledge_key") or "").strip()
    if not key:
        return None

    levels = knowledge_levels(actor)
    before = _safe_int(levels.get(key), 0)
    mode = str(resolved.get("mode") or "SET").upper()
    value = _safe_int(resolved.get("value"), 0)
    if mode == "ADD":
        after = before + value
    elif mode == "MAX":
        after = max(before, value)
    elif mode == "MIN":
        after = min(before, value)
    else:
        mode = "SET"
        after = value

    if resolved.get("min_level") is not None:
        after = max(after, _safe_int(resolved.get("min_level"), after))
    if resolved.get("max_level") is not None:
        after = min(after, _safe_int(resolved.get("max_level"), after))
    after = max(0, int(after))

    packet = set_knowledge_level(actor, key, after)
    if not packet:
        return None
    return {
        "rule_id": rule.get("id"),
        "knowledge_key": key,
        "knowledge_mode": mode,
        "knowledge_value": value,
        "knowledge_before": before,
        "knowledge_after": after,
        "knowledge_changed": before != after,
    }


def apply_player_actor_consequences(actor, action):
    """Apply ACTOR Knowledge consequences to a real Character that has no Siza npc_id."""
    if not actor:
        return {"status": "NO_ACTOR", "build": PLAYER_RECIPIENT_BUILD, "results": []}
    if str(getattr(actor.db, "npc_id", "") or "").strip():
        return {
            "status": "NPC_ACTOR_USES_CORE_CONSEQUENCE_ENGINE",
            "build": PLAYER_RECIPIENT_BUILD,
            "results": [],
        }

    packet = dict(action or {})
    action_id = str(packet.get("action_id") or "").strip()
    if not action_id:
        return {"status": "BAD_ACTION", "build": PLAYER_RECIPIENT_BUILD, "results": []}

    applied_ids = [str(value) for value in _plain_list(getattr(actor.db, APPLIED_ACTIONS_ATTR, []))]
    if action_id in applied_ids:
        return {
            "status": "ALREADY_APPLIED",
            "action_id": action_id,
            "build": PLAYER_RECIPIENT_BUILD,
            "results": [],
        }

    results = []
    for rule in consequence_rules():
        if not bool(rule.get("enabled", False)):
            continue
        if str(rule.get("recipient_mode") or "ACTION_RECIPIENTS").upper() != "ACTOR":
            continue
        when = _plain_dict(rule.get("when"))
        if when and not _condition_matches(packet, when):
            continue
        result = _knowledge_result(actor, rule, packet)
        if result:
            results.append(result)

    if not results:
        return {
            "status": "NO_MATCHING_PLAYER_CONSEQUENCE",
            "action_id": action_id,
            "build": PLAYER_RECIPIENT_BUILD,
            "results": [],
        }

    applied_ids.append(action_id)
    setattr(actor.db, APPLIED_ACTIONS_ATTR, applied_ids[-APPLIED_ACTIONS_LIMIT:])
    return {
        "status": "APPLIED",
        "action_id": action_id,
        "actor_dbref": int(actor.id),
        "actor_name": actor.key,
        "build": PLAYER_RECIPIENT_BUILD,
        "results": results,
    }
