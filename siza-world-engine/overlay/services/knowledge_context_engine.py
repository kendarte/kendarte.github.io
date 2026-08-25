KNOWLEDGE_CONTEXT_BUILD = "0.28.0-knowledge-aware-decisions"
FACT_LIFECYCLE_BUILD = "1.01.0-holder-local-fact-lifecycle-authority"
FACT_STATUS_ACTIVE = "ACTIVE"
FACT_STATUS_RETRACTED = "RETRACTED"
FACT_STATUS_SUPERSEDED = "SUPERSEDED"
_ALLOWED_FACT_STATUSES = {
    FACT_STATUS_ACTIVE,
    FACT_STATUS_RETRACTED,
    FACT_STATUS_SUPERSEDED,
}


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


def _normalize_compare(key, value):
    if key in {"type", "source"}:
        return str(value or "").upper()
    return str(value or "")


def _condition_matches(goal, when):
    item = dict(goal or {})
    for key, expected in _plain_dict(when).items():
        actual = item.get(key)
        if isinstance(expected, (list, tuple, set)):
            wanted = {_normalize_compare(key, value) for value in expected}
            if _normalize_compare(key, actual) not in wanted:
                return False
            continue
        if _normalize_compare(key, actual) != _normalize_compare(key, expected):
            return False
    return True


def knowledge_levels(npc):
    if not npc:
        return {}
    output = {}
    for key, value in _plain_dict(getattr(npc.db, "knowledge", {})).items():
        try:
            output[str(key)] = int(value or 0)
        except (TypeError, ValueError):
            output[str(key)] = 0
    return output


def knowledge_facts(npc):
    if not npc:
        return []
    output = []
    for raw in _plain_list(getattr(npc.db, "knowledge_facts", [])):
        item = _record(raw)
        if item is not None and item.get("id"):
            output.append(item)
    return output


def _effects(fact):
    output = []
    for raw in _plain_list((fact or {}).get("decision_effects")):
        item = _record(raw)
        if item is not None:
            output.append(item)
    return output


def fact_lifecycle_state(fact):
    raw_status = str((fact or {}).get("fact_status") or FACT_STATUS_ACTIVE).strip().upper()
    valid_status = raw_status in _ALLOWED_FACT_STATUSES
    status = raw_status if valid_status else "INVALID"
    active = bool(valid_status and status == FACT_STATUS_ACTIVE)
    return {
        "fact_status": status,
        "fact_status_raw": raw_status,
        "fact_status_valid": bool(valid_status),
        "fact_active": active,
        "fact_status_reason": (fact or {}).get("fact_status_reason"),
        "fact_status_changed_at": (fact or {}).get("fact_status_changed_at"),
        "superseded_by_fact_id": (fact or {}).get("superseded_by_fact_id"),
        "fact_lifecycle_build": FACT_LIFECYCLE_BUILD,
    }


def fact_knowledge_state(npc, fact):
    knowledge_key = str((fact or {}).get("knowledge_key") or "").strip()
    try:
        required = int((fact or {}).get("required_level", 1) or 1)
    except (TypeError, ValueError):
        required = 1
    level = int(knowledge_levels(npc).get(knowledge_key, 0) or 0) if knowledge_key else 0
    level_known = bool(knowledge_key and level >= required)
    lifecycle = fact_lifecycle_state(fact)
    return {
        "knowledge_key": knowledge_key or None,
        "level": level,
        "required_level": required,
        "level_known": level_known,
        "known": bool(level_known and lifecycle.get("fact_active")),
        **lifecycle,
    }


def knowledge_decision_modifiers(npc, goal):
    """Apply only explicit effects carried by currently active Facts the NPC knows."""
    output = []
    if not npc:
        return output

    for fact in knowledge_facts(npc):
        state = fact_knowledge_state(npc, fact)
        if not state.get("known"):
            continue
        fact_id = str(fact.get("id") or "")
        for effect in _effects(fact):
            if not bool(effect.get("enabled", False)):
                continue
            when = _plain_dict(effect.get("when"))
            if when and not _condition_matches(goal, when):
                continue
            try:
                value = int(effect.get("value", 0) or 0)
            except (TypeError, ValueError):
                value = 0
            if not value:
                continue
            output.append(
                {
                    "id": str(effect.get("id") or f"KNOWLEDGE_EFFECT:{fact_id}"),
                    "value": value,
                    "source": "knowledge",
                    "fact_id": fact_id,
                    "knowledge_key": state.get("knowledge_key"),
                    "knowledge_level": state.get("level"),
                    "required_level": state.get("required_level"),
                    "when": when,
                }
            )
    return output


def inspect_knowledge_context(npc):
    rows = []
    if not npc:
        return {
            "build": KNOWLEDGE_CONTEXT_BUILD,
            "fact_lifecycle_build": FACT_LIFECYCLE_BUILD,
            "npc": None,
            "npc_id": None,
            "levels": {},
            "facts": [],
        }

    for fact in knowledge_facts(npc):
        state = fact_knowledge_state(npc, fact)
        rows.append(
            {
                "fact_id": fact.get("id"),
                "topic": fact.get("topic"),
                "knowledge_key": state.get("knowledge_key"),
                "knowledge_level": state.get("level"),
                "required_level": state.get("required_level"),
                "level_known": state.get("level_known"),
                "known": state.get("known"),
                "fact_status": state.get("fact_status"),
                "fact_active": state.get("fact_active"),
                "superseded_by_fact_id": state.get("superseded_by_fact_id"),
                "decision_effects": _effects(fact),
                "canon_status": fact.get("canon_status") or fact.get("status") or "prototype",
            }
        )

    return {
        "build": KNOWLEDGE_CONTEXT_BUILD,
        "fact_lifecycle_build": FACT_LIFECYCLE_BUILD,
        "npc": npc.key,
        "npc_id": str(getattr(npc.db, "npc_id", "") or ""),
        "levels": knowledge_levels(npc),
        "facts": rows,
    }


def set_knowledge_effect_active(npc, effect_id, active):
    if not npc:
        return None
    wanted = str(effect_id or "").strip()
    facts = knowledge_facts(npc)
    found = None

    for fact_index, fact in enumerate(facts):
        effects = _effects(fact)
        changed = False
        for effect_index, effect in enumerate(effects):
            if str(effect.get("id") or "") != wanted:
                continue
            effect["enabled"] = bool(active)
            effects[effect_index] = effect
            found = {
                "fact_id": fact.get("id"),
                "effect": dict(effect),
                **fact_knowledge_state(npc, fact),
            }
            changed = True
        if changed:
            fact["decision_effects"] = effects
            facts[fact_index] = fact

    if found is None:
        return None
    npc.db.knowledge_facts = facts
    return found


def set_knowledge_level(npc, knowledge_key, level):
    if not npc:
        return None
    key = str(knowledge_key or "").strip()
    if not key:
        return None
    try:
        new_level = max(0, int(level))
    except (TypeError, ValueError):
        return None

    levels = knowledge_levels(npc)
    before = int(levels.get(key, 0) or 0)
    levels[key] = new_level
    npc.db.knowledge = levels
    return {
        "knowledge_key": key,
        "before": before,
        "after": new_level,
    }
