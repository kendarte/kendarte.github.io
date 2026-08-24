from datetime import datetime, timezone

from evennia import create_script, search_script

from services.npc_simulation import simulated_npcs


CONSEQUENCE_BUILD = "0.29.0-action-consequence-knowledge"
REGISTRY_KEY = "SIZA_CONSEQUENCE_REGISTRY"
ACTION_LOG_LIMIT = 50
PROCESSED_LIMIT = 200
MEMORY_LIMIT = 100


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


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def get_consequence_registry(create=False):
    matches = list(search_script(REGISTRY_KEY))
    registry = matches[0] if matches else None
    if registry is None and create:
        registry = create_script(
            "typeclasses.consequence_registry.SizaConsequenceRegistry",
            key=REGISTRY_KEY,
            persistent=True,
            autostart=True,
        )
    if registry is not None:
        if registry.db.rules is None:
            registry.db.rules = []
        if registry.db.processed_action_ids is None:
            registry.db.processed_action_ids = []
        if registry.db.action_log is None:
            registry.db.action_log = []
        registry.db.build = CONSEQUENCE_BUILD
    return registry


def consequence_rules():
    registry = get_consequence_registry(create=False)
    if registry is None:
        return []
    output = []
    for raw in _plain_list(registry.db.rules):
        item = _record(raw)
        if item is not None and item.get("id"):
            output.append(item)
    return output


def upsert_consequence_rule(rule):
    item = _record(rule)
    rule_id = str((item or {}).get("id") or "").strip()
    if not rule_id:
        return None
    item["id"] = rule_id
    item.setdefault("enabled", False)
    item.setdefault("canon_status", "prototype")
    item.setdefault("recipient_mode", "ACTION_RECIPIENTS")

    registry = get_consequence_registry(create=True)
    output = []
    replaced = False
    for current in consequence_rules():
        if str(current.get("id") or "") == rule_id:
            output.append(dict(item))
            replaced = True
        else:
            output.append(dict(current))
    if not replaced:
        output.append(dict(item))
    registry.db.rules = output
    registry.db.build = CONSEQUENCE_BUILD
    return dict(item)


def set_consequence_rule_active(rule_id, active):
    registry = get_consequence_registry(create=False)
    if registry is None:
        return None
    wanted = str(rule_id or "").strip()
    output = []
    found = None
    for current in consequence_rules():
        item = dict(current)
        if str(item.get("id") or "") == wanted:
            item["enabled"] = bool(active)
            found = dict(item)
        output.append(item)
    if found is None:
        return None
    registry.db.rules = output
    return found


def _normalize_compare(key, value):
    if key in {"action_type", "goal_type", "type", "source"}:
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
    """Resolve $fields recursively through normal and Evennia persistent containers."""
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


def _npc_map():
    output = {}
    for npc in simulated_npcs():
        npc_id = str(getattr(npc.db, "npc_id", "") or "").strip()
        if npc_id:
            output[npc_id] = npc
    return output


def _recipient_ids(rule, action):
    mode = str((rule or {}).get("recipient_mode") or "ACTION_RECIPIENTS").upper()
    if mode == "EXPLICIT":
        values = _plain_list((rule or {}).get("recipient_ids"))
    elif mode == "ACTOR":
        actor_id = str((action or {}).get("actor_npc_id") or "").strip()
        values = [actor_id] if actor_id else []
    elif mode == "TARGET":
        target_id = str((action or {}).get("target_npc_id") or "").strip()
        values = [target_id] if target_id else []
    else:
        values = _plain_list((action or {}).get("recipient_ids"))
    return [str(value) for value in values if value]


def _upsert_effect(effects, effect):
    effect_id = str((effect or {}).get("id") or "").strip()
    output = []
    replaced = False
    for raw in _plain_list(effects):
        item = _record(raw)
        if item is None:
            continue
        if effect_id and str(item.get("id") or "") == effect_id:
            output.append(dict(effect))
            replaced = True
        else:
            output.append(item)
    if not replaced:
        output.append(dict(effect))
    return output


def _apply_memory_consequence(rule, action, npc):
    spec = _plain_dict((rule or {}).get("memory"))
    if not spec or not npc:
        return None

    now = datetime.now(timezone.utc).isoformat()
    npc_id = str(getattr(npc.db, "npc_id", "") or "")
    actor_id = str((action or {}).get("actor_npc_id") or (action or {}).get("issuer_id") or "")
    actor_name = (action or {}).get("actor_name") or (action or {}).get("issuer_name")
    memory_id = str(
        _resolve_template(spec.get("memory_id"), action)
        or f"AUTO-MEMORY:{rule.get('id')}:{npc_id}"
    )

    effect_spec = _plain_dict(spec.get("decision_effect"))
    effect = None
    if effect_spec:
        effect = _resolve_template(effect_spec, action)
        effect = _plain_dict(effect)
        effect.setdefault("id", f"AUTO-EFFECT:{rule.get('id')}:{npc_id}")
        effect.setdefault("enabled", True)
        effect.setdefault("kind", "CONTEXT_BIAS")
        effect.setdefault("canon_status", rule.get("canon_status") or "prototype")

    memories = []
    found = False
    created = False
    before_occurrences = 0
    after_occurrences = 1

    for raw in _plain_list(getattr(npc.db, "memories", [])):
        item = _record(raw)
        if item is None:
            continue
        current_id = str(item.get("id") or item.get("memory_id") or "")
        if current_id != memory_id:
            memories.append(item)
            continue

        found = True
        before_occurrences = int(item.get("occurrences", 1) or 1)
        after_occurrences = before_occurrences + 1
        item["occurrences"] = after_occurrences
        item["last_action_id"] = action.get("action_id")
        item["last_action_at"] = action.get("timestamp") or now
        item["last_occurrence"] = action.get("occurrence")
        item["subject_npc_id"] = actor_id or item.get("subject_npc_id")
        item["with_name"] = actor_name or item.get("with_name")
        if spec.get("summary"):
            item["summary"] = str(_resolve_template(spec.get("summary"), action))
        if effect:
            item["decision_effects"] = _upsert_effect(item.get("decision_effects"), effect)
        memories.append(item)

    if not found:
        created = True
        memory = {
            "id": memory_id,
            "type": str(spec.get("type") or "world_consequence"),
            "schema": int(spec.get("schema", 3) or 3),
            "timestamp": action.get("timestamp") or now,
            "first_action_id": action.get("action_id"),
            "last_action_id": action.get("action_id"),
            "last_action_at": action.get("timestamp") or now,
            "last_occurrence": action.get("occurrence"),
            "occurrences": 1,
            "subject_npc_id": actor_id or None,
            "with_name": actor_name,
            "summary": str(_resolve_template(spec.get("summary"), action) or "Consecuencia persistente del mundo."),
            "canon_status": rule.get("canon_status") or "prototype",
            "action_type": action.get("action_type"),
        }
        if effect:
            memory["decision_effects"] = [effect]
        memories.append(memory)

    npc.db.memories = memories[-MEMORY_LIMIT:]
    return {
        "npc_id": npc_id,
        "npc_name": npc.key,
        "memory_id": memory_id,
        "created": created,
        "occurrences_before": before_occurrences,
        "occurrences_after": after_occurrences,
        "decision_effect_id": effect.get("id") if effect else None,
        "decision_effect_value": effect.get("value") if effect else None,
    }


def _apply_knowledge_consequence(rule, action, npc):
    """Apply an explicit persistent Knowledge mutation to one resolved recipient."""
    spec = _plain_dict((rule or {}).get("knowledge"))
    if not spec or not npc:
        return None

    resolved = _resolve_template(spec, action)
    resolved = _plain_dict(resolved)
    knowledge_key = str(resolved.get("knowledge_key") or "").strip()
    if not knowledge_key:
        return None

    mode = str(resolved.get("mode") or "SET").upper()
    value = _safe_int(resolved.get("value"), 0)
    levels = _plain_dict(getattr(npc.db, "knowledge", {}))
    before = _safe_int(levels.get(knowledge_key), 0)

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

    levels[knowledge_key] = after
    npc.db.knowledge = levels
    return {
        "npc_id": str(getattr(npc.db, "npc_id", "") or ""),
        "npc_name": npc.key,
        "knowledge_key": knowledge_key,
        "knowledge_mode": mode,
        "knowledge_value": value,
        "knowledge_before": before,
        "knowledge_after": after,
        "knowledge_changed": before != after,
    }


def emit_world_action(action):
    """Evaluate one structured world action exactly once against active consequence rules."""
    packet = _record(action) or {}
    action_type = str(packet.get("action_type") or "").upper().strip()
    action_id = str(packet.get("action_id") or "").strip()
    if not action_type or not action_id:
        return {"status": "BAD_ACTION", "action_id": action_id, "action_type": action_type, "results": []}

    packet["action_type"] = action_type
    packet.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    registry = get_consequence_registry(create=False)
    if registry is None:
        return {"status": "NO_REGISTRY", "action_id": action_id, "action_type": action_type, "results": []}

    processed = [str(value) for value in _plain_list(registry.db.processed_action_ids)]
    if action_id in processed:
        return {"status": "ALREADY_PROCESSED", "action_id": action_id, "action_type": action_type, "results": []}

    npcs = _npc_map()
    rule_results = []
    for rule in consequence_rules():
        if not bool(rule.get("enabled", False)):
            continue
        when = _plain_dict(rule.get("when"))
        if when and not _condition_matches(packet, when):
            continue

        applied = []
        for recipient_id in _recipient_ids(rule, packet):
            npc = npcs.get(recipient_id)
            if not npc:
                applied.append({"npc_id": recipient_id, "status": "RECIPIENT_NOT_FOUND"})
                continue

            row = {
                "npc_id": recipient_id,
                "npc_name": npc.key,
                "status": "APPLIED",
            }
            memory_result = _apply_memory_consequence(rule, packet, npc)
            knowledge_result = _apply_knowledge_consequence(rule, packet, npc)
            if memory_result:
                row.update(memory_result)
                row["memory_applied"] = True
            if knowledge_result:
                row.update(knowledge_result)
                row["knowledge_applied"] = True
            if row.get("memory_applied") or row.get("knowledge_applied"):
                applied.append(row)

        rule_results.append(
            {
                "rule_id": rule.get("id"),
                "status": "APPLIED" if applied else "NO_RECIPIENTS",
                "applied": applied,
            }
        )

    processed.append(action_id)
    registry.db.processed_action_ids = processed[-PROCESSED_LIMIT:]
    log = _plain_list(registry.db.action_log)
    log.append(
        {
            "action_id": action_id,
            "action_type": action_type,
            "timestamp": packet.get("timestamp"),
            "actor_npc_id": packet.get("actor_npc_id"),
            "actor_name": packet.get("actor_name"),
            "order_id": packet.get("order_id"),
            "task_id": packet.get("task_id"),
            "job_id": packet.get("job_id"),
            "occurrence": packet.get("occurrence"),
            "recipient_ids": _plain_list(packet.get("recipient_ids")),
            "rule_results": rule_results,
        }
    )
    registry.db.action_log = log[-ACTION_LOG_LIMIT:]
    registry.db.build = CONSEQUENCE_BUILD
    return {
        "status": "PROCESSED",
        "action_id": action_id,
        "action_type": action_type,
        "results": rule_results,
    }


def inspect_consequence_state():
    registry = get_consequence_registry(create=False)
    if registry is None:
        return {
            "build": CONSEQUENCE_BUILD,
            "registry_exists": False,
            "rules": [],
            "processed_action_ids": [],
            "action_log": [],
        }
    return {
        "build": CONSEQUENCE_BUILD,
        "registry_exists": True,
        "rules": consequence_rules(),
        "processed_action_ids": _plain_list(registry.db.processed_action_ids),
        "action_log": _plain_list(registry.db.action_log),
    }
