TRAIT_BUILD = "0.30.0-virtue-defect-traits"


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


def traits(npc):
    """Return persistent authored traits without assigning semantics from prose."""
    if not npc:
        return []
    output = []
    for raw in _plain_list(getattr(npc.db, "traits", [])):
        item = _record(raw)
        if item is not None and item.get("id"):
            output.append(item)
    return output


def _effects(trait):
    output = []
    for raw in _plain_list((trait or {}).get("decision_effects")):
        item = _record(raw)
        if item is not None:
            output.append(item)
    return output


def trait_decision_modifiers(npc, goal):
    """Return explicit decision effects from enabled traits matching this goal."""
    output = []
    for trait in traits(npc):
        if not bool(trait.get("enabled", False)):
            continue
        trait_id = str(trait.get("id") or "")
        trait_kind = str(trait.get("kind") or "TRAIT").upper()
        trait_name = str(trait.get("name") or trait_id)
        for effect in _effects(trait):
            if not bool(effect.get("enabled", True)):
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
                    "id": str(effect.get("id") or f"TRAIT_EFFECT:{trait_id}"),
                    "value": value,
                    "source": "trait",
                    "trait_id": trait_id,
                    "trait_name": trait_name,
                    "trait_kind": trait_kind,
                    "when": when,
                }
            )
    return output


def inspect_traits(npc):
    return {
        "build": TRAIT_BUILD,
        "npc": npc.key if npc else None,
        "npc_id": str(getattr(npc.db, "npc_id", "") or "") if npc else None,
        "traits": traits(npc),
    }


def set_trait_active(npc, trait_id, active):
    if not npc:
        return None
    wanted = str(trait_id or "").strip()
    output = []
    found = None
    for trait in traits(npc):
        item = dict(trait)
        if str(item.get("id") or "") == wanted:
            item["enabled"] = bool(active)
            found = dict(item)
        output.append(item)
    if found is None:
        return None
    npc.db.traits = output
    return found
