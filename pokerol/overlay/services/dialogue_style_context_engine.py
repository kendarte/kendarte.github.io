DIALOGUE_STYLE_CONTEXT_BUILD = "0.82.0-explicit-nonfactual-dialogue-style-context"


_STYLE_DIMENSIONS = {
    "register": {"FORMAL", "NEUTRAL", "CASUAL"},
    "warmth": {"RESERVED", "NEUTRAL", "WARM"},
    "directness": {"DIRECT", "BALANCED", "EVASIVE"},
    "verbosity": {"TERSE", "NORMAL"},
    "cadence": {"CLIPPED", "PLAIN", "MEASURED"},
}

_DEFAULT_STYLE = {
    "register": "NEUTRAL",
    "warmth": "NEUTRAL",
    "directness": "BALANCED",
    "verbosity": "NORMAL",
    "cadence": "PLAIN",
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


def _record(value):
    try:
        return {str(key): item for key, item in value.items()}
    except Exception:
        return None


def _normalize_style_value(dimension, value):
    key = str(dimension or "").strip().lower()
    normalized = str(value or "").strip().upper()
    if key not in _STYLE_DIMENSIONS:
        return None
    if normalized not in _STYLE_DIMENSIONS[key]:
        return None
    return normalized


def _apply_profile(style, raw_profile, *, source, diagnostics):
    profile = _plain_dict(raw_profile)
    for dimension in _STYLE_DIMENSIONS:
        if dimension not in profile:
            continue
        normalized = _normalize_style_value(dimension, profile.get(dimension))
        if normalized is None:
            diagnostics["ignored"].append(
                {
                    "source": source,
                    "dimension": dimension,
                    "value": str(profile.get(dimension)),
                    "reason": "INVALID_ENUM_VALUE",
                }
            )
            continue
        style[dimension] = normalized
        diagnostics["applied"].append(
            {"source": source, "dimension": dimension, "value": normalized}
        )


def _apply_trait_effects(style, npc, diagnostics):
    for raw_trait in _plain_list(getattr(npc.db, "traits", [])) if npc else []:
        trait = _record(raw_trait)
        if not trait or not bool(trait.get("enabled", False)):
            continue
        trait_id = str(trait.get("id") or "").strip()
        for raw_effect in _plain_list(trait.get("dialogue_effects")):
            effect = _record(raw_effect)
            if not effect or not bool(effect.get("enabled", True)):
                continue
            dimension = str(effect.get("dimension") or "").strip().lower()
            normalized = _normalize_style_value(dimension, effect.get("value"))
            if normalized is None:
                diagnostics["ignored"].append(
                    {
                        "source": "TRAIT_DIALOGUE_EFFECT",
                        "trait_id": trait_id,
                        "effect_id": str(effect.get("id") or ""),
                        "dimension": dimension,
                        "value": str(effect.get("value") or ""),
                        "reason": "INVALID_DIALOGUE_EFFECT",
                    }
                )
                continue
            style[dimension] = normalized
            diagnostics["applied"].append(
                {
                    "source": "TRAIT_DIALOGUE_EFFECT",
                    "trait_id": trait_id,
                    "effect_id": str(effect.get("id") or ""),
                    "dimension": dimension,
                    "value": normalized,
                }
            )


def _relationship_familiarity(npc, actor):
    if not npc or not actor:
        return 0
    try:
        actor_dbref = int(actor.id)
    except (TypeError, ValueError):
        return 0
    relationships = _plain_dict(getattr(npc.db, "relationships", {}))
    best = 0
    for raw in relationships.values():
        row = _record(raw)
        if not row:
            continue
        try:
            target_dbref = int(row.get("target_dbref"))
        except (TypeError, ValueError):
            continue
        if target_dbref != actor_dbref:
            continue
        try:
            best = max(best, int(row.get("familiarity", 0) or 0))
        except (TypeError, ValueError):
            pass
    return max(0, best)


def _familiarity_band(count):
    try:
        value = max(0, int(count or 0))
    except (TypeError, ValueError):
        value = 0
    if value <= 0:
        return "NONE"
    if value <= 2:
        return "RECENT"
    if value <= 5:
        return "FAMILIAR"
    return "ESTABLISHED"


def build_dialogue_style_context(npc, actor=None):
    """Return presentation-only style enums. Never derive facts or decision semantics from trait prose."""
    style = dict(_DEFAULT_STYLE)
    diagnostics = {"applied": [], "ignored": []}
    if npc:
        _apply_profile(
            style,
            getattr(npc.db, "dialogue_style", {}),
            source="NPC_DIALOGUE_STYLE",
            diagnostics=diagnostics,
        )
        _apply_trait_effects(style, npc, diagnostics)

    familiarity = _relationship_familiarity(npc, actor)
    safe_style = {
        **style,
        "familiarity_band": _familiarity_band(familiarity),
    }
    return {
        "build": DIALOGUE_STYLE_CONTEXT_BUILD,
        "safe_style": safe_style,
        "diagnostics": {
            **diagnostics,
            "familiarity_count": familiarity,
        },
    }
