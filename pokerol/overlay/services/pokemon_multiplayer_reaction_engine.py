"""Multiplayer-only ally protection and interception for POKEROL.

INTERCEPT is a one-shot reaction armed during COMMAND. It does not replace the
trainer's main order. When an enemy later targets the protected ally, the shared
round engine may change the real defender to the interceptor at execution time.
"""

from copy import deepcopy

from services.pokemon_battle_engine import _speed
from services.pokemon_battle_position_engine import normalized_position
from typeclasses.pokemon_battle_session import participant_id


MULTI_REACTION_BUILD = "0.1.0-real-intercept"


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


def _float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clone(value):
    return deepcopy(value)


def combatant_for_participant(combatants, participant_id_value):
    wanted = _text(participant_id_value)
    for row in combatants if isinstance(combatants, list) else _list(combatants):
        if not isinstance(row, dict):
            continue
        if _text(row.get("controller_participant_id")) == wanted and _text(row.get("controller_kind")).upper() == "HUMAN":
            return row
    return None


def ally_targets(combatants, protector_id):
    protector = next((row for row in _list(combatants) if _text(_dict(row).get("combatant_id")) == _text(protector_id)), None)
    protector = _dict(protector)
    if not protector:
        return []
    team = _text(protector.get("team")).upper()
    output = []
    for raw in _list(combatants):
        row = _dict(raw)
        if _text(row.get("combatant_id")) == _text(protector_id):
            continue
        if _text(row.get("team")).upper() != team:
            continue
        if not bool(row.get("active", True)) or bool(row.get("needs_switch")):
            continue
        pokemon = _dict(row.get("pokemon"))
        if _int(pokemon.get("hp_current"), 0) <= 0:
            continue
        output.append({
            "combatant_id": _text(row.get("combatant_id")),
            "trainer_name": _text(row.get("trainer_name")),
            "team": team,
            "pokemon_name": _text(pokemon.get("name") or pokemon.get("species_name")) or "Pokémon",
            "hp_current": _int(pokemon.get("hp_current"), 0),
            "hp_max": _int(pokemon.get("hp_max"), 1),
        })
    return output


def arm_intercept(session, actor, protected_target_id):
    if not session or not actor:
        return {"accepted": False, "status": "SESSION_OR_ACTOR_REQUIRED", "build": MULTI_REACTION_BUILD}
    if _text(session.db.status).upper() != "ACTIVE" or _text(session.db.phase).upper() != "COMMAND":
        return {"accepted": False, "status": "INTERCEPT_ONLY_DURING_COMMAND", "build": MULTI_REACTION_BUILD}
    pid = participant_id(actor)
    pending = _dict(session.db.pending_orders)
    if _dict(pending.get(pid)):
        return {"accepted": False, "status": "ORDER_ALREADY_LOCKED", "build": MULTI_REACTION_BUILD}
    combatants = _list(session.db.combatants)
    protector = combatant_for_participant(combatants, pid)
    if not protector:
        return {"accepted": False, "status": "NO_CONTROLLABLE_COMBATANT", "build": MULTI_REACTION_BUILD}
    pokemon = _dict(protector.get("pokemon"))
    if _int(pokemon.get("hp_current"), 0) <= 0 or bool(protector.get("needs_switch")):
        return {"accepted": False, "status": "PROTECTOR_NOT_ABLE", "build": MULTI_REACTION_BUILD}
    if _text(pokemon.get("status")).upper() in {"SLEEP", "FREEZE"}:
        return {"accepted": False, "status": "PROTECTOR_CANNOT_REACT", "build": MULTI_REACTION_BUILD}
    wanted = _text(protected_target_id)
    legal = {row["combatant_id"]: row for row in ally_targets(combatants, protector.get("combatant_id"))}
    if wanted not in legal:
        return {"accepted": False, "status": "INVALID_PROTECTED_TARGET", "valid_target_ids": sorted(legal), "build": MULTI_REACTION_BUILD}
    pokemon["battle_reaction"] = {
        "policy": "INTERCEPT",
        "armed": True,
        "armed_turn": max(1, _int(session.db.turn, 1)),
        "protected_target": {
            "combatant_id": wanted,
            "pokemon_name": legal[wanted]["pokemon_name"],
            "trainer_name": legal[wanted]["trainer_name"],
        },
    }
    for index, raw in enumerate(combatants):
        row = _dict(raw)
        if _text(row.get("combatant_id")) == _text(protector.get("combatant_id")):
            row["pokemon"] = pokemon
            combatants[index] = row
            break
    session.write_combatants(combatants)
    session.append_log(
        "INTERCEPT_ARMED",
        f"{pokemon.get('name') or 'Pokémon'} se prepara para proteger a {legal[wanted]['pokemon_name']}.",
        participant_id=pid,
        protector_combatant_id=protector.get("combatant_id"),
        protected_combatant_id=wanted,
    )
    return {
        "accepted": True,
        "status": "INTERCEPT_ARMED",
        "protected_target": _clone(legal[wanted]),
        "protector_combatant_id": protector.get("combatant_id"),
        "build": MULTI_REACTION_BUILD,
    }


def clear_intercept(session, actor):
    if not session or not actor:
        return {"accepted": False, "status": "SESSION_OR_ACTOR_REQUIRED", "build": MULTI_REACTION_BUILD}
    if _text(session.db.phase).upper() != "COMMAND":
        return {"accepted": False, "status": "NOT_COMMAND_PHASE", "build": MULTI_REACTION_BUILD}
    pid = participant_id(actor)
    combatants = _list(session.db.combatants)
    protector = combatant_for_participant(combatants, pid)
    if not protector:
        return {"accepted": False, "status": "NO_CONTROLLABLE_COMBATANT", "build": MULTI_REACTION_BUILD}
    pokemon = _dict(protector.get("pokemon"))
    reaction = _dict(pokemon.get("battle_reaction"))
    if _text(reaction.get("policy")).upper() != "INTERCEPT" or not bool(reaction.get("armed")):
        return {"accepted": True, "status": "NO_INTERCEPT_ARMED", "build": MULTI_REACTION_BUILD}
    pokemon["battle_reaction"] = {"policy": "NONE", "armed": False, "armed_turn": 0}
    for index, raw in enumerate(combatants):
        row = _dict(raw)
        if _text(row.get("combatant_id")) == _text(protector.get("combatant_id")):
            row["pokemon"] = pokemon
            combatants[index] = row
            break
    session.write_combatants(combatants)
    return {"accepted": True, "status": "INTERCEPT_CLEARED", "build": MULTI_REACTION_BUILD}


def _intercept_chance(attacker, interceptor):
    atk_speed = max(1.0, float(_speed(attacker)))
    int_speed = max(1.0, float(_speed(interceptor)))
    ratio = int_speed / max(1.0, atk_speed + int_speed)
    chance = 0.72 + (ratio - 0.5) * 0.45
    pos = normalized_position(interceptor)
    mobility = max(0.4, min(1.3, _float(pos.get("mobility_modifier"), 1.0)))
    chance += (mobility - 1.0) * 0.20
    if _text(interceptor.get("status")).upper() == "PARALYSIS":
        chance -= 0.16
    return max(0.30, min(0.95, chance))


def resolve_interceptor(combatants, attacker_row, original_target_row, rng):
    """Resolve a real defender substitution at attack execution time."""
    attacker = _dict(_dict(attacker_row).get("pokemon"))
    target = _dict(original_target_row)
    target_id = _text(target.get("combatant_id"))
    team = _text(target.get("team")).upper()
    candidates = []
    for raw in combatants if isinstance(combatants, list) else _list(combatants):
        row = raw if isinstance(raw, dict) else _dict(raw)
        if _text(row.get("team")).upper() != team or _text(row.get("combatant_id")) == target_id:
            continue
        if not bool(row.get("active", True)) or bool(row.get("needs_switch")):
            continue
        pokemon = _dict(row.get("pokemon"))
        if _int(pokemon.get("hp_current"), 0) <= 0:
            continue
        reaction = _dict(pokemon.get("battle_reaction"))
        protected = _dict(reaction.get("protected_target"))
        if _text(reaction.get("policy")).upper() != "INTERCEPT" or not bool(reaction.get("armed")):
            continue
        if _text(protected.get("combatant_id")) != target_id:
            continue
        if _text(pokemon.get("status")).upper() in {"SLEEP", "FREEZE"}:
            continue
        candidates.append(row)
    if not candidates:
        return {"triggered": False, "target": original_target_row, "build": MULTI_REACTION_BUILD}
    candidates.sort(key=lambda row: _speed(_dict(row.get("pokemon"))), reverse=True)
    interceptor = candidates[0]
    pokemon = _dict(interceptor.get("pokemon"))
    reaction = _dict(pokemon.get("battle_reaction"))
    chance = _intercept_chance(attacker, pokemon)
    roll = rng.random()
    pokemon["battle_reaction"] = {"policy": "NONE", "armed": False, "armed_turn": reaction.get("armed_turn", 0)}
    interceptor["pokemon"] = pokemon
    success = roll <= chance
    return {
        "triggered": True,
        "success": success,
        "status": "INTERCEPT_SUCCESS" if success else "INTERCEPT_FAILED",
        "target": interceptor if success else original_target_row,
        "interceptor_combatant_id": _text(interceptor.get("combatant_id")),
        "interceptor_name": _text(pokemon.get("name") or pokemon.get("species_name")) or "Pokémon",
        "protected_combatant_id": target_id,
        "protected_name": _text(_dict(target.get("pokemon")).get("name") or _dict(target.get("pokemon")).get("species_name")) or "Pokémon",
        "chance": chance,
        "roll": roll,
        "build": MULTI_REACTION_BUILD,
    }


def expire_unused_intercepts(combatants):
    expired = []
    for raw in combatants if isinstance(combatants, list) else _list(combatants):
        row = raw if isinstance(raw, dict) else _dict(raw)
        pokemon = _dict(row.get("pokemon"))
        reaction = _dict(pokemon.get("battle_reaction"))
        if _text(reaction.get("policy")).upper() != "INTERCEPT" or not bool(reaction.get("armed")):
            continue
        pokemon["battle_reaction"] = {"policy": "NONE", "armed": False, "armed_turn": reaction.get("armed_turn", 0)}
        row["pokemon"] = pokemon
        expired.append(_text(row.get("combatant_id")))
    return expired
