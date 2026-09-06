"""Anime-style one-shot battle reactions for POKEROL.

A reaction is armed before the main command and consumed by the next relevant
incoming attack. DODGE modifies hit probability from speed and battle position;
it never invents movement or world geometry.
"""

from copy import deepcopy

from services.pokemon_battle_position_engine import normalized_position


REACTION_BUILD = "0.1.0-dodge-reaction"
SUPPORTED_REACTIONS = {"NONE", "DODGE"}


def _dict(value):
    try:
        return dict(value or {})
    except Exception:
        return {}


def _text(value):
    return str(value or "").strip()


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def reaction_state(pokemon):
    raw = _dict(_dict(pokemon).get("battle_reaction"))
    policy = _text(raw.get("policy")).upper() or "NONE"
    if policy not in SUPPORTED_REACTIONS:
        policy = "NONE"
    return {
        "policy": policy,
        "armed": bool(raw.get("armed", False)) and policy != "NONE",
        "armed_turn": max(0, _int(raw.get("armed_turn"), 0)),
    }


def arm_reaction(battle, side="PLAYER", policy="DODGE"):
    state = battle if isinstance(battle, dict) else {}
    side_name = _text(side).upper() or "PLAYER"
    pokemon = state.get("player" if side_name == "PLAYER" else "enemy")
    if not isinstance(pokemon, dict):
        return {"accepted": False, "status": "BATTLE_PARTICIPANT_MISSING", "build": REACTION_BUILD}
    wanted = _text(policy).upper() or "NONE"
    if wanted not in SUPPORTED_REACTIONS:
        return {"accepted": False, "status": "UNSUPPORTED_REACTION", "build": REACTION_BUILD}
    if wanted == "NONE":
        pokemon["battle_reaction"] = {"policy": "NONE", "armed": False, "armed_turn": int(state.get("turn") or 0)}
        return {"accepted": True, "status": "REACTION_CLEARED", "reaction": deepcopy(pokemon["battle_reaction"]), "build": REACTION_BUILD}
    pokemon["battle_reaction"] = {
        "policy": wanted,
        "armed": True,
        "armed_turn": int(state.get("turn") or 0),
    }
    return {"accepted": True, "status": "REACTION_ARMED", "reaction": deepcopy(pokemon["battle_reaction"]), "build": REACTION_BUILD}


def clear_reaction(pokemon):
    if isinstance(pokemon, dict):
        pokemon["battle_reaction"] = {"policy": "NONE", "armed": False, "armed_turn": 0}


def _speed_estimate(pokemon):
    p = _dict(pokemon)
    base = max(1.0, _float(_dict(p.get("stats")).get("SPE"), 1.0))
    stages = _dict(p.get("battle_stages"))
    stage = max(-6, min(6, _int(stages.get("SPE"), 0)))
    stage_mult = (2.0 + stage) / 2.0 if stage >= 0 else 2.0 / (2.0 - stage)
    value = base * stage_mult
    if _text(p.get("status")).upper() == "PARALYSIS":
        value *= 0.50
    value *= max(0.4, min(1.3, _float(normalized_position(p).get("mobility_modifier"), 1.0)))
    return max(1.0, value)


def dodge_chance(attacker, defender):
    if not reaction_state(defender).get("armed") or reaction_state(defender).get("policy") != "DODGE":
        return 0.0
    atk = _speed_estimate(attacker)
    dfn = _speed_estimate(defender)
    ratio = dfn / max(1.0, atk + dfn)
    chance = 0.18 + (ratio - 0.5) * 0.70
    pos = normalized_position(defender)
    if pos.get("stance") == "AIR":
        chance += 0.08
    elif pos.get("stance") == "ELEVATED":
        chance += 0.04
    elif pos.get("stance") == "WATER" and _float(pos.get("mobility_modifier"), 1.0) < 0.9:
        chance -= 0.08
    cover = _dict(pos.get("cover"))
    chance += min(0.08, max(0.0, _float(cover.get("rating"), 0.0)) * 0.15)
    return max(0.08, min(0.62, chance))


def reaction_accuracy_multiplier(attacker, defender):
    chance = dodge_chance(attacker, defender)
    return max(0.38, min(1.0, 1.0 - chance)) if chance > 0 else 1.0


def settle_incoming_attack_reaction(battle, defender_side, log_start_index):
    """Consume an armed reaction if a real incoming MOVE was attempted.

    If the new log contains MISS, the miss is promoted to an explicit dodge event.
    Otherwise DODGE_FAILED is appended. Returns a settlement packet.
    """
    state = battle if isinstance(battle, dict) else {}
    side = _text(defender_side).upper()
    defender = state.get("player" if side == "PLAYER" else "enemy")
    if not isinstance(defender, dict):
        return {"consumed": False, "status": "NO_DEFENDER", "build": REACTION_BUILD}
    reaction = reaction_state(defender)
    if not reaction.get("armed") or reaction.get("policy") != "DODGE":
        return {"consumed": False, "status": "NO_ARMED_DODGE", "build": REACTION_BUILD}

    logs = state.get("log") if isinstance(state.get("log"), list) else []
    start = max(0, _int(log_start_index, 0))
    new_logs = logs[start:]
    defender_id = _text(defender.get("entity_id"))
    move_attempted = any(
        _text(row.get("kind")).upper() == "MOVE" and _text(row.get("actor")) != defender_id
        for row in new_logs if isinstance(row, dict)
    )
    if not move_attempted:
        return {"consumed": False, "status": "NO_INCOMING_MOVE_ATTEMPT", "build": REACTION_BUILD}

    success_row = None
    for row in reversed(new_logs):
        if not isinstance(row, dict):
            continue
        if _text(row.get("kind")).upper() == "MISS":
            success_row = row
            break
        if _text(row.get("kind")).upper() == "DAMAGE" and _text(row.get("target")) == defender_id:
            break

    name = _text(defender.get("name") or defender.get("species_name")) or "Pokémon"
    defender["battle_reaction"] = {"policy": "NONE", "armed": False, "armed_turn": reaction.get("armed_turn", 0)}
    if success_row is not None:
        success_row["kind"] = "DODGE_SUCCESS"
        success_row["text"] = f"¡{name} esquiva el ataque!"
        success_row["reaction"] = "DODGE"
        return {"consumed": True, "success": True, "status": "DODGE_SUCCESS", "build": REACTION_BUILD}

    logs.append({
        "turn": int(state.get("turn") or 1),
        "phase": str(state.get("phase") or "REACTION"),
        "kind": "DODGE_FAILED",
        "text": f"{name} intenta esquivar, pero no logra salir de la trayectoria.",
        "target": defender_id,
        "reaction": "DODGE",
    })
    return {"consumed": True, "success": False, "status": "DODGE_FAILED", "build": REACTION_BUILD}
