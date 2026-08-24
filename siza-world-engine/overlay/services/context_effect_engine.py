CONTEXT_EFFECT_BUILD = "0.26.0-memory-relationship-context"


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


def _effects(container):
    output = []
    for raw in _plain_list((container or {}).get("decision_effects")):
        item = _record(raw)
        if item is not None:
            output.append(item)
    return output


def _memories(npc):
    output = []
    if not npc:
        return output
    for raw in _plain_list(getattr(npc.db, "memories", [])):
        item = _record(raw)
        if item is not None:
            output.append(item)
    return output


def _relationships(npc):
    return _plain_dict(getattr(npc.db, "relationships", {})) if npc else {}


def context_decision_modifiers(npc, goal):
    """Return explicit decision effects authored into persistent memories/relationships.

    No sentiment is inferred from prose. Only enabled decision_effects whose exact
    metadata conditions match the current goal are applied.
    """
    output = []
    if not npc:
        return output

    for memory in _memories(npc):
        memory_id = str(memory.get("id") or memory.get("memory_id") or "")
        for effect in _effects(memory):
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
                    "id": str(effect.get("id") or f"MEMORY_EFFECT:{memory_id}"),
                    "value": value,
                    "source": "memory",
                    "memory_id": memory_id or None,
                    "memory_type": memory.get("type"),
                    "subject_npc_id": memory.get("subject_npc_id"),
                    "when": when,
                }
            )

    for identity, raw_relation in _relationships(npc).items():
        relation = _record(raw_relation) or {}
        for effect in _effects(relation):
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
                    "id": str(effect.get("id") or f"RELATIONSHIP_EFFECT:{identity}"),
                    "value": value,
                    "source": "relationship",
                    "relationship_identity": str(identity),
                    "target_npc_id": relation.get("target_npc_id") or (str(identity) if not str(identity).startswith("DBREF:") else None),
                    "target_name": relation.get("target_name") or relation.get("name"),
                    "when": when,
                }
            )

    return output


def inspect_context_effects(npc):
    rows = []
    if not npc:
        return rows

    for memory in _memories(npc):
        memory_id = str(memory.get("id") or memory.get("memory_id") or "")
        for effect in _effects(memory):
            rows.append(
                {
                    "source": "MEMORY",
                    "container_id": memory_id or None,
                    "container_type": memory.get("type"),
                    "subject_npc_id": memory.get("subject_npc_id"),
                    "subject_name": memory.get("with_name") or memory.get("subject_name"),
                    "effect": effect,
                }
            )

    for identity, raw_relation in _relationships(npc).items():
        relation = _record(raw_relation) or {}
        for effect in _effects(relation):
            rows.append(
                {
                    "source": "RELATIONSHIP",
                    "container_id": str(identity),
                    "container_type": relation.get("target_type") or "RELATIONSHIP",
                    "subject_npc_id": relation.get("target_npc_id") or (str(identity) if not str(identity).startswith("DBREF:") else None),
                    "subject_name": relation.get("target_name") or relation.get("name"),
                    "effect": effect,
                }
            )
    return rows


def set_context_effect_active(npc, effect_id, active):
    """Toggle one nested memory/relationship decision effect by stable effect id."""
    if not npc:
        return None
    wanted = str(effect_id or "").strip()
    desired = bool(active)

    memories = _memories(npc)
    for memory_index, memory in enumerate(memories):
        effects = _effects(memory)
        for effect_index, effect in enumerate(effects):
            if str(effect.get("id") or "") != wanted:
                continue
            effect["enabled"] = desired
            effects[effect_index] = effect
            memory["decision_effects"] = effects
            memories[memory_index] = memory
            npc.db.memories = memories[-100:]
            return {"source": "MEMORY", "effect": dict(effect), "container_id": memory.get("id") or memory.get("memory_id")}

    relationships = _relationships(npc)
    for identity, raw_relation in list(relationships.items()):
        relation = _record(raw_relation) or {}
        effects = _effects(relation)
        for effect_index, effect in enumerate(effects):
            if str(effect.get("id") or "") != wanted:
                continue
            effect["enabled"] = desired
            effects[effect_index] = effect
            relation["decision_effects"] = effects
            relationships[str(identity)] = relation
            npc.db.relationships = relationships
            return {"source": "RELATIONSHIP", "effect": dict(effect), "container_id": str(identity)}
    return None
