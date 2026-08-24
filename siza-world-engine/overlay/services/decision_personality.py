from services.context_effect_engine import context_decision_modifiers
from services.faction_engine import faction_context_modifiers
from services.knowledge_context_engine import knowledge_decision_modifiers
from services.trait_engine import trait_decision_modifiers


DECISION_PERSONALITY_BUILD = "0.30.0-virtue-defect-traits"

MIN_MODIFIER = -100
MAX_MODIFIER = 100
MIN_EFFECTIVE_PRIORITY = -999
MAX_EFFECTIVE_PRIORITY = 999


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


def _clamp(value, low, high):
    return max(low, min(high, int(value)))


def _normalize_compare(key, value):
    if key in {"type", "source"}:
        return str(value or "").upper()
    return str(value or "")


def _condition_matches(goal, when):
    """Exact data-driven matching over existing goal metadata."""
    goal = goal or {}
    for key, expected in _plain_dict(when).items():
        actual = goal.get(key)
        if isinstance(expected, (list, tuple, set)):
            wanted = {_normalize_compare(key, item) for item in expected}
            if _normalize_compare(key, actual) not in wanted:
                return False
            continue
        if _normalize_compare(key, actual) != _normalize_compare(key, expected):
            return False
    return True


def decision_modifiers(npc):
    """Return authored personality/decision modifiers without changing state."""
    output = []
    if not npc:
        return output
    for raw in _plain_list(getattr(npc.db, "decision_modifiers", [])):
        item = _record(raw)
        if item is not None:
            output.append(item)
    return output


def decision_biases(npc):
    """Optional simple per-goal-type biases; modifiers are the richer form."""
    if not npc:
        return {}
    output = {}
    for key, value in _plain_dict(getattr(npc.db, "decision_biases", {})).items():
        output[str(key).upper()] = _clamp(_safe_int(value, 0), MIN_MODIFIER, MAX_MODIFIER)
    return output


def apply_decision_personality(npc, goal, base_priority=None):
    """Apply personality plus explicit faction, memory, relationship, knowledge and trait context."""
    item = dict(goal or {})
    goal_type = str(item.get("type") or "").upper()
    if base_priority is None:
        base_priority = item.get("priority", 0)
    base = _safe_int(base_priority, 0)

    applied = []
    authored_total = 0
    faction_total = 0
    memory_total = 0
    relationship_total = 0
    knowledge_total = 0
    trait_total = 0

    type_bias = decision_biases(npc).get(goal_type, 0)
    if type_bias:
        authored_total += type_bias
        applied.append(
            {
                "id": f"BIAS:{goal_type}",
                "value": type_bias,
                "source": "decision_biases",
            }
        )

    for modifier in decision_modifiers(npc):
        if not bool(modifier.get("enabled", False)):
            continue
        when = _plain_dict(modifier.get("when"))
        if when and not _condition_matches(item, when):
            continue
        value = _clamp(_safe_int(modifier.get("value"), 0), MIN_MODIFIER, MAX_MODIFIER)
        if not value:
            continue
        authored_total += value
        applied.append(
            {
                "id": str(modifier.get("id") or "UNNAMED_MODIFIER"),
                "value": value,
                "source": "decision_modifiers",
            }
        )

    for modifier in faction_context_modifiers(npc, item):
        value = _clamp(_safe_int(modifier.get("value"), 0), MIN_MODIFIER, MAX_MODIFIER)
        if not value:
            continue
        faction_total += value
        applied.append(
            {
                "id": str(modifier.get("id") or "FACTION_CONTEXT"),
                "value": value,
                "source": modifier.get("source") or "faction_membership",
                "faction_id": modifier.get("faction_id"),
                "role": modifier.get("role"),
                "rank": modifier.get("rank"),
            }
        )

    for modifier in context_decision_modifiers(npc, item):
        value = _clamp(_safe_int(modifier.get("value"), 0), MIN_MODIFIER, MAX_MODIFIER)
        if not value:
            continue
        source = str(modifier.get("source") or "context").lower()
        if source == "memory":
            memory_total += value
        elif source == "relationship":
            relationship_total += value
        applied.append(
            {
                "id": str(modifier.get("id") or "CONTEXT_EFFECT"),
                "value": value,
                "source": source,
                "memory_id": modifier.get("memory_id"),
                "relationship_identity": modifier.get("relationship_identity"),
                "subject_npc_id": modifier.get("subject_npc_id"),
                "target_npc_id": modifier.get("target_npc_id"),
            }
        )

    for modifier in knowledge_decision_modifiers(npc, item):
        value = _clamp(_safe_int(modifier.get("value"), 0), MIN_MODIFIER, MAX_MODIFIER)
        if not value:
            continue
        knowledge_total += value
        applied.append(
            {
                "id": str(modifier.get("id") or "KNOWLEDGE_CONTEXT"),
                "value": value,
                "source": "knowledge",
                "fact_id": modifier.get("fact_id"),
                "knowledge_key": modifier.get("knowledge_key"),
                "knowledge_level": modifier.get("knowledge_level"),
                "required_level": modifier.get("required_level"),
            }
        )

    for modifier in trait_decision_modifiers(npc, item):
        value = _clamp(_safe_int(modifier.get("value"), 0), MIN_MODIFIER, MAX_MODIFIER)
        if not value:
            continue
        trait_total += value
        applied.append(
            {
                "id": str(modifier.get("id") or "TRAIT_CONTEXT"),
                "value": value,
                "source": "trait",
                "trait_id": modifier.get("trait_id"),
                "trait_name": modifier.get("trait_name"),
                "trait_kind": modifier.get("trait_kind"),
            }
        )

    total = authored_total + faction_total + memory_total + relationship_total + knowledge_total + trait_total
    effective = _clamp(base + total, MIN_EFFECTIVE_PRIORITY, MAX_EFFECTIVE_PRIORITY)
    item["base_priority"] = base
    item["authored_personality_modifier"] = authored_total
    item["faction_loyalty_modifier"] = faction_total
    item["memory_modifier"] = memory_total
    item["relationship_context_modifier"] = relationship_total
    item["knowledge_modifier"] = knowledge_total
    item["trait_modifier"] = trait_total
    item["personality_modifier"] = total
    item["effective_priority"] = effective
    item["priority"] = effective
    item["priority_modifiers"] = applied
    return item


def effective_priority(npc, goal, base_priority=None):
    return int(apply_decision_personality(npc, goal, base_priority=base_priority).get("priority", 0))


def set_decision_modifier_active(npc, modifier_id, active):
    if not npc:
        return None
    wanted = str(modifier_id or "").strip()
    output = []
    found = None
    for raw in decision_modifiers(npc):
        item = dict(raw)
        if str(item.get("id") or "") == wanted:
            item["enabled"] = bool(active)
            found = dict(item)
        output.append(item)
    if found is None:
        return None
    npc.db.decision_modifiers = output
    return found


def inspect_decision_personality(npc):
    return {
        "build": DECISION_PERSONALITY_BUILD,
        "npc": npc.key if npc else None,
        "npc_id": getattr(npc.db, "npc_id", None) if npc else None,
        "decision_priorities": _plain_dict(getattr(npc.db, "decision_priorities", {})) if npc else {},
        "decision_biases": decision_biases(npc),
        "decision_modifiers": decision_modifiers(npc),
    }
