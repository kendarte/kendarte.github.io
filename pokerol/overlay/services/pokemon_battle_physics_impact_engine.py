"""Translate authoritative world-physics impacts into Pokémon battle HP/status.

World physics decides what shared medium was affected. This bridge decides which
virtual battle participants occupy that medium and applies Pokémon combat math.
"""

import math
import random
from copy import deepcopy

from services.pokemon_battle_engine import type_multiplier
from services.pokemon_battle_status_engine import apply_move_effects, effective_stat


IMPACT_BUILD = "0.1.0-shared-medium-battle-impact"
ELECTRIC_WORLD_EFFECTS = {"ELECTRIFY", "SHORT_CIRCUIT", "ELECTRIC_SHOCK"}


def _dict(value):
    try:
        return dict(value or {})
    except Exception:
        return {}


def _list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _text(value):
    return str(value or "").strip()


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _types(value):
    return [str(v).strip().upper() for v in _list(value) if str(v).strip()]


def _electric_discharge(move):
    effects = {str(v).strip().upper() for v in _list(_dict(move).get("world_effects")) if str(v).strip()}
    return _text(_dict(move).get("pokemon_type")).upper() == "ELECTRIC" and bool(effects & ELECTRIC_WORLD_EFFECTS)


def _medium_damage(attacker, defender, move, rng):
    power = max(0, _int(_dict(move).get("power"), 0))
    damage_class = _text(_dict(move).get("damage_class")).upper()
    if power <= 0 or damage_class == "STATUS":
        return 0, type_multiplier("ELECTRIC", _types(defender.get("types"))), False
    attack = effective_stat(attacker, "ATK" if damage_class == "PHYSICAL" else "SPA")
    defense = effective_stat(defender, "DEF" if damage_class == "PHYSICAL" else "SPD")
    level = max(1, _int(attacker.get("level"), 1))
    base = math.floor((math.floor((2 * level) / 5) + 2) * power * attack / max(1, defense) / 50) + 2
    stab = 1.5 if "ELECTRIC" in _types(attacker.get("types")) else 1.0
    effectiveness = type_multiplier("ELECTRIC", defender.get("types"))
    critical = rng.random() < (1.0 / 16.0)
    # Shared-water discharge disperses some energy but remains dangerous to every occupant.
    modifier = 0.90 * stab * effectiveness * (1.5 if critical else 1.0) * rng.uniform(0.85, 1.0)
    return max(0, math.floor(base * modifier)), effectiveness, critical


def _event(kind, text, **extra):
    row = {"kind": kind, "text": text}
    row.update({key: value for key, value in extra.items() if value is not None})
    return row


def apply_world_physics_to_battle(battle, move, world_result, *, rng=None):
    """Mutate battle participants hit by one verified shared-medium world effect."""
    state = battle if isinstance(battle, dict) else {}
    move = _dict(move)
    result = _dict(world_result)
    medium_id = _text(result.get("target_water_body_id"))
    if not bool(result.get("executed")) or not medium_id:
        return {"applied": False, "status": "NO_SHARED_MEDIUM_IMPACT", "impacts": [], "build": IMPACT_BUILD}
    if not _electric_discharge(move):
        return {"applied": False, "status": "NO_BATTLE_ELECTRIC_DISCHARGE", "impacts": [], "build": IMPACT_BUILD}

    rng = rng or random.SystemRandom()
    attacker_id = _text(_dict(state.get("player")).get("entity_id"))
    attacker = _dict(state.get("player"))
    if _text(_dict(state.get("enemy")).get("entity_id")) == _text(result.get("actor_entity_id")):
        attacker = _dict(state.get("enemy"))
    elif _text(result.get("actor_entity_id")) and _text(result.get("actor_entity_id")) != attacker_id:
        for side in ("player", "enemy"):
            candidate = _dict(state.get(side))
            if _text(candidate.get("entity_id")) == _text(result.get("actor_entity_id")):
                attacker = candidate
                break

    impacts = []
    for side in ("player", "enemy"):
        participant = state.get(side)
        if not isinstance(participant, dict):
            continue
        if _text(participant.get("contact_medium_id")) != medium_id:
            continue
        if _int(participant.get("hp_current"), 0) <= 0:
            continue

        damage, effectiveness, critical = _medium_damage(attacker, participant, move, rng)
        name = _text(participant.get("name") or participant.get("species_name")) or "Pokémon"
        events = []
        if effectiveness == 0:
            events.append(_event("MEDIUM_IMMUNE", f"La descarga no afecta a {name}.", effectiveness=0))
        else:
            if damage > 0:
                participant["hp_current"] = max(0, _int(participant.get("hp_current"), 0) - damage)
                events.append(_event(
                    "MEDIUM_ELECTRIC_DAMAGE",
                    f"La electricidad se propaga por el agua: {name} recibe {damage} de daño.",
                    damage=damage,
                    effectiveness=effectiveness,
                    critical=critical,
                ))
            if _int(participant.get("hp_current"), 0) > 0:
                events.extend(apply_move_effects(attacker, participant, move, rng))

        impacts.append({
            "side": side.upper(),
            "entity_id": participant.get("entity_id"),
            "medium_id": medium_id,
            "damage": damage,
            "effectiveness": effectiveness,
            "critical": critical,
            "hp_current": participant.get("hp_current"),
            "events": deepcopy(events),
        })

    return {
        "applied": bool(impacts),
        "status": "SHARED_MEDIUM_BATTLE_IMPACT" if impacts else "NO_BATTLE_PARTICIPANT_IN_MEDIUM",
        "medium_id": medium_id,
        "impacts": impacts,
        "build": IMPACT_BUILD,
    }
