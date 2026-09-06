"""Anime-style one-shot battle reactions for POKEROL.

Reactions are explicit server-authorized policies. DODGE is natural mobility.
REDIRECT/BLOCK require an active move that can physically perform the defense and
consume one PP only when a compatible incoming move actually triggers them.
INTERCEPT is exposed only when the battle declares a real protected target.
"""

from copy import deepcopy

from services.pokemon_battle_position_engine import normalized_position


REACTION_BUILD = "0.3.0-anime-defensive-reactions"
SUPPORTED_REACTIONS = {"NONE", "DODGE", "REDIRECT", "BLOCK", "INTERCEPT"}

PROJECTILE_LIKE = {"PROJECTILE", "PARABOLA", "ARC", "RAIN"}
BARRIER_DELIVERIES = {"CONTACT", "MOVEMENT", "PROJECTILE", "BEAM", "PARABOLA", "ARC", "RAIN", "WAVE", "CONE", "TARGETED"}
SHELTER_DELIVERIES = {"PROJECTILE", "BEAM", "PARABOLA", "ARC", "RAIN", "WAVE", "CONE"}


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


def _upper_set(value):
    return {str(v).strip().upper() for v in _list(value) if str(v).strip()}


def _moves(pokemon):
    return [_dict(row) for row in _list(_dict(pokemon).get("moves")) if _dict(row)]


def _move_by_id(pokemon, move_id):
    wanted = _text(move_id).upper()
    for move in _moves(pokemon):
        if _text(move.get("move_id")).upper() == wanted:
            return move
    return None


def _move_pp_ready(move):
    return bool(move) and _int(_dict(move).get("pp_current"), _dict(move).get("pp", 0)) > 0


def _defense_methods(move):
    """Return reaction methods this authored move can support."""
    move = _dict(move)
    if not _move_pp_ready(move):
        return []
    profile = _text(move.get("defense_profile")).upper() or "NONE"
    effects = _upper_set(move.get("world_effects"))
    damage_class = _text(move.get("damage_class")).upper()
    rows = []

    if profile == "REDIRECT":
        rows.append({"policy": "REDIRECT", "allowed_deliveries": sorted(BARRIER_DELIVERIES), "base_chance": 0.62})
    elif profile == "REFLECT":
        rows.append({"policy": "REDIRECT", "allowed_deliveries": sorted(PROJECTILE_LIKE | {"BEAM"}), "base_chance": 0.72})
    elif profile == "BRUSH":
        rows.append({"policy": "REDIRECT", "allowed_deliveries": sorted(PROJECTILE_LIKE), "base_chance": 0.66})
    elif profile == "BARRIER":
        rows.append({"policy": "BLOCK", "allowed_deliveries": sorted(BARRIER_DELIVERIES), "base_chance": 0.68})
    elif profile == "SHELTER":
        rows.append({"policy": "BLOCK", "allowed_deliveries": sorted(SHELTER_DELIVERIES), "base_chance": 0.62})
    elif profile == "ABSORB":
        rows.append({"policy": "BLOCK", "allowed_deliveries": sorted(BARRIER_DELIVERIES), "base_chance": 0.64})

    # Kanto prototype fallback: world semantics can authorize a reaction even
    # before the Creator has explicit defense_profile values for every move.
    if "CREATE_WIND" in effects and not any(row["policy"] == "REDIRECT" for row in rows):
        rows.append({"policy": "REDIRECT", "allowed_deliveries": sorted(PROJECTILE_LIKE), "base_chance": 0.64})
    if "TELEKINESIS" in effects and not any(row["policy"] == "REDIRECT" for row in rows):
        rows.append({"policy": "REDIRECT", "allowed_deliveries": sorted(PROJECTILE_LIKE), "base_chance": 0.70})
    if "HARDEN_BODY" in effects and not any(row["policy"] == "BLOCK" for row in rows):
        rows.append({
            "policy": "BLOCK",
            "allowed_deliveries": ["CONTACT", "MOVEMENT", "PROJECTILE"],
            "base_chance": 0.56,
            "physical_only": True,
        })

    output = []
    for row in rows:
        output.append({
            **row,
            "method_move_id": _text(move.get("move_id")),
            "method_move_name": _text(move.get("name")) or _text(move.get("move_id")),
            "pp_current": _int(move.get("pp_current"), move.get("pp", 0)),
            "pp_max": _int(move.get("pp_max"), move.get("pp", 0)),
            "defense_profile": profile,
            "damage_class": damage_class,
        })
    return output


def reaction_options(battle, side="PLAYER"):
    state = _dict(battle)
    side_name = _text(side).upper() or "PLAYER"
    pokemon = _dict(state.get("player" if side_name == "PLAYER" else "enemy"))
    if not pokemon or _int(pokemon.get("hp_current"), 0) <= 0:
        return []
    status = _text(pokemon.get("status")).upper() or "OK"
    output = []
    if status not in {"SLEEP", "FREEZE"}:
        output.append({
            "policy": "DODGE",
            "label": "ESQUIVAR",
            "natural": True,
            "method_move_id": "",
            "method_move_name": "",
            "pp_cost": 0,
        })
        for move in _moves(pokemon):
            for method in _defense_methods(move):
                output.append({
                    **deepcopy(method),
                    "label": "DESVIAR" if method["policy"] == "REDIRECT" else "BLOQUEAR",
                    "natural": False,
                    "pp_cost": 1,
                })

    protected = _dict(state.get("protected_target"))
    if protected and status not in {"SLEEP", "FREEZE"}:
        output.append({
            "policy": "INTERCEPT",
            "label": "INTERCEPTAR",
            "natural": True,
            "method_move_id": "",
            "method_move_name": "",
            "pp_cost": 0,
            "protected_target": deepcopy(protected),
        })

    seen = set()
    rows = []
    for row in output:
        key = (_text(row.get("policy")), _text(row.get("method_move_id")))
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return rows


def reaction_state(pokemon):
    raw = _dict(_dict(pokemon).get("battle_reaction"))
    policy = _text(raw.get("policy")).upper() or "NONE"
    if policy not in SUPPORTED_REACTIONS:
        policy = "NONE"
    return {
        "policy": policy,
        "armed": bool(raw.get("armed", False)) and policy != "NONE",
        "armed_turn": max(0, _int(raw.get("armed_turn"), 0)),
        "method_move_id": _text(raw.get("method_move_id")),
        "method_move_name": _text(raw.get("method_move_name")),
        "allowed_deliveries": sorted(_upper_set(raw.get("allowed_deliveries"))),
        "base_chance": max(0.0, min(1.0, _float(raw.get("base_chance"), 0.0))),
        "physical_only": bool(raw.get("physical_only", False)),
        "incoming_delivery": _text(raw.get("incoming_delivery")).upper(),
        "incoming_damage_class": _text(raw.get("incoming_damage_class")).upper(),
        "protected_target": deepcopy(_dict(raw.get("protected_target"))),
    }


def arm_reaction(battle, side="PLAYER", policy="DODGE", method_move_id=""):
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

    method_id = _text(method_move_id)
    option = None
    for row in reaction_options(state, side_name):
        if _text(row.get("policy")).upper() != wanted:
            continue
        if _text(row.get("method_move_id")) != method_id:
            continue
        option = row
        break
    if not option:
        return {
            "accepted": False,
            "status": "REACTION_METHOD_NOT_AUTHORIZED",
            "policy": wanted,
            "method_move_id": method_id,
            "build": REACTION_BUILD,
        }

    pokemon["battle_reaction"] = {
        "policy": wanted,
        "armed": True,
        "armed_turn": int(state.get("turn") or 0),
        "method_move_id": _text(option.get("method_move_id")),
        "method_move_name": _text(option.get("method_move_name")),
        "allowed_deliveries": deepcopy(_list(option.get("allowed_deliveries"))),
        "base_chance": _float(option.get("base_chance"), 0.0),
        "physical_only": bool(option.get("physical_only", False)),
        "protected_target": deepcopy(_dict(option.get("protected_target"))),
    }
    return {"accepted": True, "status": "REACTION_ARMED", "reaction": reaction_state(pokemon), "build": REACTION_BUILD}


def clear_reaction(pokemon):
    if isinstance(pokemon, dict):
        pokemon["battle_reaction"] = {"policy": "NONE", "armed": False, "armed_turn": 0}


def set_incoming_reaction_context(defender, move):
    """Temporarily declare the verified incoming move before hit calculation."""
    if not isinstance(defender, dict):
        return
    raw = _dict(defender.get("battle_reaction"))
    if not bool(raw.get("armed")):
        return
    move = _dict(move)
    raw["incoming_delivery"] = _text(move.get("delivery")).upper()
    raw["incoming_damage_class"] = _text(move.get("damage_class")).upper()
    raw["incoming_move_id"] = _text(move.get("move_id"))
    defender["battle_reaction"] = raw


def clear_incoming_reaction_context(defender):
    if not isinstance(defender, dict):
        return
    raw = _dict(defender.get("battle_reaction"))
    raw.pop("incoming_delivery", None)
    raw.pop("incoming_damage_class", None)
    raw.pop("incoming_move_id", None)
    defender["battle_reaction"] = raw


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


def _method_ready(defender, reaction):
    method_id = _text(_dict(reaction).get("method_move_id"))
    if not method_id:
        return True
    return _move_pp_ready(_move_by_id(defender, method_id))


def _incoming_compatible(defender, reaction):
    r = _dict(reaction)
    if not _method_ready(defender, r):
        return False
    delivery = _text(r.get("incoming_delivery")).upper()
    allowed = _upper_set(r.get("allowed_deliveries"))
    if allowed and delivery not in allowed:
        return False
    if bool(r.get("physical_only")) and _text(r.get("incoming_damage_class")).upper() != "PHYSICAL":
        return False
    return True


def dodge_chance(attacker, defender):
    reaction = reaction_state(defender)
    if not reaction.get("armed") or reaction.get("policy") != "DODGE":
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


def defensive_move_chance(attacker, defender):
    reaction = reaction_state(defender)
    if not reaction.get("armed") or reaction.get("policy") not in {"REDIRECT", "BLOCK"}:
        return 0.0
    if not _incoming_compatible(defender, reaction):
        return 0.0
    atk = _speed_estimate(attacker)
    dfn = _speed_estimate(defender)
    ratio = dfn / max(1.0, atk + dfn)
    base = _float(reaction.get("base_chance"), 0.58)
    chance = base + (ratio - 0.5) * 0.35
    if reaction.get("policy") == "BLOCK":
        pos = normalized_position(defender)
        cover = _dict(pos.get("cover"))
        chance += min(0.07, max(0.0, _float(cover.get("rating"), 0.0)) * 0.12)
    return max(0.18, min(0.88, chance))


def reaction_accuracy_multiplier(attacker, defender):
    reaction = reaction_state(defender)
    if not reaction.get("armed"):
        return 1.0
    if reaction.get("policy") == "DODGE":
        chance = dodge_chance(attacker, defender)
    elif reaction.get("policy") in {"REDIRECT", "BLOCK"}:
        chance = defensive_move_chance(attacker, defender)
    else:
        chance = 0.0
    return max(0.12, min(1.0, 1.0 - chance)) if chance > 0 else 1.0


def _move_for_actor(state, actor_id, move_id):
    for side in ("player", "enemy"):
        pokemon = _dict(state.get(side))
        if _text(pokemon.get("entity_id")) != _text(actor_id):
            continue
        return _move_by_id(pokemon, move_id) or {}
    return {}


def _consume_reaction_pp(defender, reaction):
    method_id = _text(_dict(reaction).get("method_move_id"))
    if not method_id:
        return {"consumed": False, "pp_cost": 0}
    move = _move_by_id(defender, method_id)
    if not _move_pp_ready(move):
        return {"consumed": False, "pp_cost": 0, "status": "REACTION_NO_PP"}
    before = _int(move.get("pp_current"), move.get("pp", 0))
    move["pp_current"] = max(0, before - 1)
    return {"consumed": True, "pp_cost": 1, "move_id": method_id, "pp_before": before, "pp_current": move["pp_current"]}


def settle_incoming_attack_reaction(battle, defender_side, log_start_index):
    """Consume and narrate one compatible armed reaction after attack resolution."""
    state = battle if isinstance(battle, dict) else {}
    side = _text(defender_side).upper()
    defender = state.get("player" if side == "PLAYER" else "enemy")
    if not isinstance(defender, dict):
        return {"consumed": False, "status": "NO_DEFENDER", "build": REACTION_BUILD}
    reaction = reaction_state(defender)
    if not reaction.get("armed"):
        return {"consumed": False, "status": "NO_ARMED_REACTION", "build": REACTION_BUILD}

    logs = state.get("log") if isinstance(state.get("log"), list) else []
    start = max(0, _int(log_start_index, 0))
    new_logs = logs[start:]
    defender_id = _text(defender.get("entity_id"))
    move_row = next((
        row for row in new_logs
        if isinstance(row, dict)
        and _text(row.get("kind")).upper() == "MOVE"
        and _text(row.get("actor")) != defender_id
    ), None)
    if not move_row:
        return {"consumed": False, "status": "NO_INCOMING_MOVE_ATTEMPT", "build": REACTION_BUILD}

    move = _move_for_actor(state, move_row.get("actor"), move_row.get("move_id"))
    if _text(move.get("delivery")).upper() == "SELF":
        clear_incoming_reaction_context(defender)
        return {"consumed": False, "status": "INCOMING_MOVE_IS_SELF", "build": REACTION_BUILD}

    policy = reaction.get("policy")
    if policy in {"REDIRECT", "BLOCK"} and not _incoming_compatible(defender, reaction):
        clear_incoming_reaction_context(defender)
        return {"consumed": False, "status": "REACTION_NOT_COMPATIBLE_WITH_MOVE", "build": REACTION_BUILD}
    if policy == "INTERCEPT":
        clear_incoming_reaction_context(defender)
        return {"consumed": False, "status": "INTERCEPT_TARGET_PIPELINE_NOT_ACTIVE", "build": REACTION_BUILD}

    success_row = None
    damage_row = None
    for row in reversed(new_logs):
        if not isinstance(row, dict):
            continue
        if _text(row.get("kind")).upper() == "MISS":
            success_row = row
            break
        if _text(row.get("kind")).upper() == "DAMAGE" and _text(row.get("target")) == defender_id:
            damage_row = row
            break

    name = _text(defender.get("name") or defender.get("species_name")) or "Pokémon"
    pp_result = _consume_reaction_pp(defender, reaction) if policy in {"REDIRECT", "BLOCK"} else {"consumed": False, "pp_cost": 0}
    clear_reaction(defender)

    if success_row is not None:
        if policy == "DODGE":
            kind, text = "DODGE_SUCCESS", f"¡{name} esquiva el ataque!"
        elif policy == "REDIRECT":
            method = reaction.get("method_move_name") or reaction.get("method_move_id") or "su defensa"
            kind, text = "REDIRECT_SUCCESS", f"¡{name} desvía el ataque con {method}!"
        else:
            method = reaction.get("method_move_name") or reaction.get("method_move_id") or "su defensa"
            kind, text = "BLOCK_SUCCESS", f"¡{name} bloquea el ataque con {method}!"
        success_row["kind"] = kind
        success_row["text"] = text
        success_row["reaction"] = policy
        success_row["reaction_move_id"] = reaction.get("method_move_id") or None
        success_row["reaction_pp"] = deepcopy(pp_result)
        return {"consumed": True, "success": True, "status": kind, "pp": pp_result, "build": REACTION_BUILD}

    if policy == "DODGE":
        kind = "DODGE_FAILED"
        text = f"{name} intenta esquivar, pero no logra salir de la trayectoria."
    elif policy == "REDIRECT":
        kind = "REDIRECT_FAILED"
        text = f"{name} intenta desviar el ataque, pero la trayectoria se mantiene."
    else:
        kind = "BLOCK_FAILED"
        text = f"{name} intenta bloquear el ataque, pero el golpe atraviesa la defensa."
    logs.append({
        "turn": int(state.get("turn") or 1),
        "phase": str(state.get("phase") or "REACTION"),
        "kind": kind,
        "text": text,
        "target": defender_id,
        "reaction": policy,
        "reaction_move_id": reaction.get("method_move_id") or None,
        "reaction_pp": deepcopy(pp_result),
        "damage": damage_row.get("damage") if damage_row else None,
    })
    return {"consumed": True, "success": False, "status": kind, "pp": pp_result, "build": REACTION_BUILD}
