"""Server-authoritative Pokémon battle core for POKEROL.

The browser is presentation/input only. This module owns battle state, command
validation, ordering, hit checks, PP, damage, status/stages, capture/run and the
battle log. World/terrain side-effects are emitted as ordered requests for the
World Engine rather than being silently mutated here.
"""

from __future__ import annotations

import math
import random
from copy import deepcopy
from time import time
from uuid import uuid4

from services.pokemon_battle_position_engine import position_move_gate
from services.pokemon_battle_reaction_engine import set_incoming_reaction_context
from services.pokemon_battle_status_engine import (
    accuracy_multiplier,
    apply_move_effects,
    before_action,
    effective_stat,
    end_turn_effects,
    normalize_battle_conditions,
)


BATTLE_BUILD = "0.4.0-position-reaction-core"
PHASES = (
    "INTRO", "COMMAND", "ORDER", "ACTION", "REACTION", "RESOLUTION",
    "END_CHECK", "SWITCH", "COMPLETE",
)
ACTIVE_STATUS = "ACTIVE"
COMPLETE_STATUS = "COMPLETE"
ACTION_TYPES = {"MOVE", "CAPTURE", "RUN", "SWITCH", "ITEM", "FREE_ORDER"}

TYPE_EFFECT = {
    ("NORMAL", "ROCK"): 0.5, ("NORMAL", "GHOST"): 0.0, ("NORMAL", "STEEL"): 0.5,
    ("FIRE", "FIRE"): 0.5, ("FIRE", "WATER"): 0.5, ("FIRE", "GRASS"): 2.0,
    ("FIRE", "ICE"): 2.0, ("FIRE", "BUG"): 2.0, ("FIRE", "ROCK"): 0.5,
    ("FIRE", "DRAGON"): 0.5, ("FIRE", "STEEL"): 2.0,
    ("WATER", "FIRE"): 2.0, ("WATER", "WATER"): 0.5, ("WATER", "GRASS"): 0.5,
    ("WATER", "GROUND"): 2.0, ("WATER", "ROCK"): 2.0, ("WATER", "DRAGON"): 0.5,
    ("ELECTRIC", "WATER"): 2.0, ("ELECTRIC", "ELECTRIC"): 0.5,
    ("ELECTRIC", "GRASS"): 0.5, ("ELECTRIC", "GROUND"): 0.0,
    ("ELECTRIC", "FLYING"): 2.0, ("ELECTRIC", "DRAGON"): 0.5,
    ("GRASS", "FIRE"): 0.5, ("GRASS", "WATER"): 2.0, ("GRASS", "GRASS"): 0.5,
    ("GRASS", "POISON"): 0.5, ("GRASS", "GROUND"): 2.0, ("GRASS", "FLYING"): 0.5,
    ("GRASS", "BUG"): 0.5, ("GRASS", "ROCK"): 2.0, ("GRASS", "DRAGON"): 0.5,
    ("GRASS", "STEEL"): 0.5,
    ("ICE", "FIRE"): 0.5, ("ICE", "WATER"): 0.5, ("ICE", "GRASS"): 2.0,
    ("ICE", "ICE"): 0.5, ("ICE", "GROUND"): 2.0, ("ICE", "FLYING"): 2.0,
    ("ICE", "DRAGON"): 2.0, ("ICE", "STEEL"): 0.5,
    ("FIGHTING", "NORMAL"): 2.0, ("FIGHTING", "ICE"): 2.0, ("FIGHTING", "POISON"): 0.5,
    ("FIGHTING", "FLYING"): 0.5, ("FIGHTING", "PSYCHIC"): 0.5,
    ("FIGHTING", "BUG"): 0.5, ("FIGHTING", "ROCK"): 2.0, ("FIGHTING", "GHOST"): 0.0,
    ("FIGHTING", "DARK"): 2.0, ("FIGHTING", "STEEL"): 2.0, ("FIGHTING", "FAIRY"): 0.5,
    ("POISON", "GRASS"): 2.0, ("POISON", "POISON"): 0.5, ("POISON", "GROUND"): 0.5,
    ("POISON", "ROCK"): 0.5, ("POISON", "GHOST"): 0.5, ("POISON", "STEEL"): 0.0,
    ("POISON", "FAIRY"): 2.0,
    ("GROUND", "FIRE"): 2.0, ("GROUND", "ELECTRIC"): 2.0, ("GROUND", "GRASS"): 0.5,
    ("GROUND", "POISON"): 2.0, ("GROUND", "FLYING"): 0.0, ("GROUND", "BUG"): 0.5,
    ("GROUND", "ROCK"): 2.0, ("GROUND", "STEEL"): 2.0,
    ("FLYING", "ELECTRIC"): 0.5, ("FLYING", "GRASS"): 2.0, ("FLYING", "FIGHTING"): 2.0,
    ("FLYING", "BUG"): 2.0, ("FLYING", "ROCK"): 0.5, ("FLYING", "STEEL"): 0.5,
    ("PSYCHIC", "FIGHTING"): 2.0, ("PSYCHIC", "POISON"): 2.0,
    ("PSYCHIC", "PSYCHIC"): 0.5, ("PSYCHIC", "DARK"): 0.0, ("PSYCHIC", "STEEL"): 0.5,
    ("BUG", "FIRE"): 0.5, ("BUG", "GRASS"): 2.0, ("BUG", "FIGHTING"): 0.5,
    ("BUG", "POISON"): 0.5, ("BUG", "FLYING"): 0.5, ("BUG", "PSYCHIC"): 2.0,
    ("BUG", "GHOST"): 0.5, ("BUG", "DARK"): 2.0, ("BUG", "STEEL"): 0.5,
    ("BUG", "FAIRY"): 0.5,
    ("ROCK", "FIRE"): 2.0, ("ROCK", "ICE"): 2.0, ("ROCK", "FIGHTING"): 0.5,
    ("ROCK", "GROUND"): 0.5, ("ROCK", "FLYING"): 2.0, ("ROCK", "BUG"): 2.0,
    ("ROCK", "STEEL"): 0.5,
    ("GHOST", "NORMAL"): 0.0, ("GHOST", "PSYCHIC"): 2.0, ("GHOST", "GHOST"): 2.0,
    ("GHOST", "DARK"): 0.5,
    ("DRAGON", "DRAGON"): 2.0, ("DRAGON", "STEEL"): 0.5, ("DRAGON", "FAIRY"): 0.0,
    ("DARK", "FIGHTING"): 0.5, ("DARK", "PSYCHIC"): 2.0, ("DARK", "GHOST"): 2.0,
    ("DARK", "DARK"): 0.5, ("DARK", "FAIRY"): 0.5,
    ("STEEL", "FIRE"): 0.5, ("STEEL", "WATER"): 0.5, ("STEEL", "ELECTRIC"): 0.5,
    ("STEEL", "ICE"): 2.0, ("STEEL", "ROCK"): 2.0, ("STEEL", "STEEL"): 0.5,
    ("STEEL", "FAIRY"): 2.0,
    ("FAIRY", "FIRE"): 0.5, ("FAIRY", "FIGHTING"): 2.0, ("FAIRY", "POISON"): 0.5,
    ("FAIRY", "DRAGON"): 2.0, ("FAIRY", "DARK"): 2.0, ("FAIRY", "STEEL"): 0.5,
}


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


def _types(value):
    return [str(v).strip().upper() for v in _list(value) if str(v).strip()]


def _clone(value):
    return deepcopy(value)


def _sprite(profile):
    raw = _dict(profile.get("sprite"))
    return {
        "front": _text(raw.get("front")),
        "back": _text(raw.get("back")),
        "icon": _text(raw.get("icon")),
        "scale": max(0.25, min(4.0, _float(raw.get("scale"), 1.0))),
    }


def _derived_stats(profile):
    level = max(1, _int(profile.get("level"), 1))
    base = _dict(profile.get("base_stats"))
    hp = max(1, math.floor((2 * _int(base.get("HP"), 40) * level) / 100) + level + 10)
    out = {"HP": hp}
    for key in ("ATK", "DEF", "SPA", "SPD", "SPE"):
        out[key] = max(1, math.floor((2 * _int(base.get(key), 40) * level) / 100) + 5)
    return out


def normalize_pokemon(profile, *, side="PLAYER"):
    p = _dict(profile)
    stats = _derived_stats(p)
    hp_max = max(1, _int(p.get("hp_max"), stats["HP"]))
    hp_current = max(0, min(hp_max, _int(p.get("hp_current"), hp_max)))
    moves = []
    active_ids = []
    for raw in _list(p.get("moves") or p.get("resolved_moves")):
        move = _dict(raw)
        move_id = _text(move.get("move_id"))
        if not move_id:
            continue
        active_ids.append(move_id)
        pp_max = max(0, _int(move.get("pp_max"), move.get("pp", 20)))
        pp_current = max(0, min(pp_max, _int(move.get("pp_current"), pp_max)))
        moves.append({
            "move_id": move_id,
            "name": _text(move.get("name")) or move_id,
            "pokemon_type": (_text(move.get("pokemon_type") or move.get("type")) or "Normal").upper(),
            "damage_class": (_text(move.get("damage_class")) or "PHYSICAL").upper(),
            "power": max(0, _int(move.get("power"), 0)),
            "accuracy": max(1, min(100, _int(move.get("accuracy"), 100))),
            "priority": _int(move.get("priority"), 0),
            "pp": pp_max,
            "pp_max": pp_max,
            "pp_current": pp_current,
            "battle_effects": _clone(_list(move.get("battle_effects"))),
            "world_enabled": bool(move.get("world_enabled", False)),
            "world_effects": [str(v) for v in _list(move.get("world_effects")) if str(v)],
            "materials": [str(v) for v in _list(move.get("materials")) if str(v)],
            "delivery": _text(move.get("delivery")),
            "defense_profile": _text(move.get("defense_profile")) or "NONE",
            "requirements": _dict(move.get("requirements")),
            "world_rules": _clone(_list(move.get("world_rules"))),
        })
    known = []
    for move_id in _list(p.get("known_moves")) + active_ids:
        move_id = _text(move_id)
        if move_id and move_id not in known:
            known.append(move_id)
    result = {
        "entity_id": _text(p.get("entity_id")) or f"PKMN:{uuid4().hex[:10].upper()}",
        "species_id": _text(p.get("species_id")),
        "name": _text(p.get("nickname") or p.get("species_name") or p.get("name")) or "Pokémon",
        "species_name": _text(p.get("species_name") or p.get("name")) or "Pokémon",
        "level": max(1, _int(p.get("level"), 1)),
        "types": _types(p.get("types")) or ["NORMAL"],
        "stats": stats,
        "hp_max": hp_max,
        "hp_current": hp_current,
        "status": _text(p.get("status")).upper() or "OK",
        "status_turns": max(0, _int(p.get("status_turns"), 0)),
        "battle_stages": _clone(_dict(p.get("battle_stages"))),
        "volatile_status": _clone(_dict(p.get("volatile_status"))),
        "side": str(side or "PLAYER").upper(),
        "known_moves": known,
        "moves": moves,
        "sprite": _sprite(p),
        "trainer": _dict(p.get("trainer")),
        "wild": bool(p.get("wild", str(side).upper() == "ENEMY")),
        "battle_tags": [str(v) for v in _list(p.get("battle_tags")) if str(v)],
    }
    return normalize_battle_conditions(result)


def _site_packet(site):
    raw = _dict(site)
    return {
        "room_id": _text(raw.get("room_id")),
        "name": _text(raw.get("name")),
        "terrain": [str(v) for v in _list(raw.get("terrain")) if str(v)],
        "weather": _text(raw.get("weather")) or "mild",
        "water_bodies": _clone(_list(raw.get("water_bodies"))),
        "world_state": _clone(_dict(raw.get("world_state"))),
        "scene_image": _clone(_dict(raw.get("scene_image"))),
    }


def create_battle(player_pokemon, enemy_pokemon, *, site=None, battle_kind="WILD", source_event_id=""):
    player = normalize_pokemon(player_pokemon, side="PLAYER")
    enemy = normalize_pokemon(enemy_pokemon, side="ENEMY")
    battle = {
        "build": BATTLE_BUILD,
        "battle_id": f"PKB-{uuid4().hex[:14].upper()}",
        "battle_kind": str(battle_kind or "WILD").upper(),
        "status": ACTIVE_STATUS,
        "phase": "INTRO",
        "turn": 1,
        "player": player,
        "enemy": enemy,
        "site": _site_packet(site),
        "source_event_id": _text(source_event_id),
        "pending_player_action": None,
        "log": [],
        "world_requests": [],
        "created_at": int(time()),
        "updated_at": int(time()),
        "outcome": "",
    }
    _log(battle, "INTRO", f"{enemy['name']} aparece.", actor=enemy["entity_id"])
    battle["phase"] = "COMMAND"
    return battle


def _log(battle, kind, text, **extra):
    row = {"turn": int(battle.get("turn", 1)), "phase": str(battle.get("phase") or ""), "kind": kind, "text": text}
    row.update({k: v for k, v in extra.items() if v is not None})
    battle.setdefault("log", []).append(row)
    if len(battle["log"]) > 100:
        battle["log"] = battle["log"][-100:]
    return row


def _append_events(battle, events, actor=None, target=None):
    for event in events or []:
        row = _dict(event)
        _log(battle, _text(row.get("kind")) or "BATTLE_EFFECT", _text(row.get("text")) or "Efecto de batalla.", actor=actor, target=target, **{k: v for k, v in row.items() if k not in {"kind", "text"}})


def move_by_id(pokemon, move_id):
    wanted = _text(move_id).upper()
    moves = pokemon.get("moves") if isinstance(pokemon, dict) else None
    for move in moves if isinstance(moves, list) else []:
        if isinstance(move, dict) and _text(move.get("move_id")).upper() == wanted:
            return move
    return None


def _struggle_move():
    return {
        "move_id": "STRUGGLE", "name": "Struggle", "pokemon_type": "NORMAL",
        "damage_class": "PHYSICAL", "power": 50, "accuracy": 100, "priority": 0,
        "pp": 1, "pp_max": 1, "pp_current": 1, "battle_effects": [],
        "world_enabled": False, "world_effects": [], "materials": ["CREATURE"],
        "delivery": "CONTACT", "defense_profile": "NONE", "requirements": {}, "world_rules": [],
    }


def type_multiplier(move_type, defender_types):
    total = 1.0
    atk = str(move_type or "NORMAL").upper()
    for dtype in _types(defender_types):
        total *= TYPE_EFFECT.get((atk, dtype), 1.0)
    return total


def _damage(attacker, defender, move, rng):
    power = max(0, _int(move.get("power"), 0))
    damage_class = _text(move.get("damage_class")).upper()
    if power <= 0 or damage_class == "STATUS":
        return 0, 1.0, False
    attack = effective_stat(attacker, "ATK" if damage_class == "PHYSICAL" else "SPA")
    defense = effective_stat(defender, "DEF" if damage_class == "PHYSICAL" else "SPD")
    level = max(1, _int(attacker.get("level"), 1))
    base = math.floor((math.floor((2 * level) / 5) + 2) * power * attack / max(1, defense) / 50) + 2
    stab = 1.5 if _text(move.get("pokemon_type")).upper() in _types(attacker.get("types")) else 1.0
    effectiveness = type_multiplier(move.get("pokemon_type"), defender.get("types"))
    critical = rng.random() < (1.0 / 16.0)
    modifier = stab * effectiveness * (1.5 if critical else 1.0) * rng.uniform(0.85, 1.0)
    return max(0, math.floor(base * modifier)), effectiveness, critical


def _enemy_action(battle, rng):
    enemy = battle.get("enemy") if isinstance(battle.get("enemy"), dict) else {}
    moves = [m for m in enemy.get("moves", []) if isinstance(m, dict) and _int(m.get("pp_current"), m.get("pp", 0)) > 0]
    if not moves:
        return {"type": "MOVE", "move_id": "STRUGGLE"}
    damaging = [m for m in moves if _int(m.get("power"), 0) > 0]
    pool = damaging or moves
    move = rng.choice(pool)
    return {"type": "MOVE", "move_id": _text(move.get("move_id"))}


def _action_priority(action, pokemon):
    kind = _text(_dict(action).get("type")).upper()
    if kind in {"CAPTURE", "SWITCH", "ITEM", "RUN"}:
        return 6
    if kind == "MOVE" or (kind == "FREE_ORDER" and _text(_dict(action).get("move_id"))):
        move = move_by_id(pokemon, _dict(action).get("move_id")) or (_struggle_move() if _text(_dict(action).get("move_id")).upper() == "STRUGGLE" else {})
        return _int(_dict(move).get("priority"), 0)
    return 0


def _speed(pokemon):
    return effective_stat(pokemon, "SPE")


def _order_actions(battle, player_action, enemy_action, rng):
    rows = [
        {"side": "PLAYER", "action": _dict(player_action), "pokemon": battle.get("player") or {}},
        {"side": "ENEMY", "action": _dict(enemy_action), "pokemon": battle.get("enemy") or {}},
    ]
    for row in rows:
        row["priority"] = _action_priority(row["action"], row["pokemon"])
        row["speed"] = _speed(row["pokemon"])
        row["tie"] = rng.random()
    rows.sort(key=lambda r: (r["priority"], r["speed"], r["tie"]), reverse=True)
    return rows


def _queue_world_request(battle, actor, target, move, command):
    move = _dict(move)
    world_target = _dict(_dict(command).get("world_target"))
    if not world_target or not bool(move.get("world_enabled")) or not _list(move.get("world_effects")):
        return
    battle.setdefault("world_requests", []).append({
        "request_id": f"WORLD-{battle['battle_id']}-{battle['turn']}-{len(battle.get('world_requests') or []) + 1}",
        "battle_id": battle["battle_id"],
        "turn": battle["turn"],
        "actor_entity_id": actor.get("entity_id"),
        "target_entity_id": target.get("entity_id") if target else "",
        "move_id": move.get("move_id"),
        "delivery": move.get("delivery"),
        "world_effects": _clone(_list(move.get("world_effects"))),
        "materials": _clone(_list(move.get("materials"))),
        "world_target": _clone(world_target),
        "intensity": max(0.1, min(3.0, _float(_dict(command).get("intensity"), 1.0))),
        "status": "PENDING_WORLD_RESOLUTION",
    })


def _prepare_move_action(battle, attacker, requested_id, rng):
    synthetic = _text(requested_id).upper() == "STRUGGLE"
    move = _struggle_move() if synthetic else move_by_id(attacker, requested_id)
    if not move:
        _log(battle, "INVALID_MOVE", f"{attacker['name']} no conoce ese movimiento.", actor=attacker["entity_id"])
        return None, synthetic
    if not synthetic:
        current_pp = _int(move.get("pp_current"), move.get("pp", 0))
        if current_pp <= 0:
            _log(battle, "NO_PP", f"{move['name']} no tiene PP.", actor=attacker["entity_id"], move_id=move["move_id"])
            return None, synthetic
        move["pp_current"] = current_pp - 1
    return move, synthetic


def _position_block_text(attacker, defender, gate):
    status = _text(_dict(gate).get("status")) or "TARGET_OUT_OF_REACH"
    if status == "TARGET_OUT_OF_REACH_AIR":
        return f"{defender.get('name') or 'El objetivo'} está fuera del alcance: se encuentra en el aire."
    if status == "TARGET_OUT_OF_REACH_ELEVATED":
        return f"{defender.get('name') or 'El objetivo'} está fuera del alcance desde esa altura."
    if status == "ATTACKER_NOT_GROUNDED":
        return f"{attacker.get('name') or 'El Pokémon'} necesita apoyo en el suelo para ejecutar ese movimiento."
    if status == "WATER_POSITION_REQUIRED":
        return "Ese movimiento necesita una posición vinculada al agua."
    return "La posición actual impide que el movimiento alcance el objetivo."


def _execute_move(battle, side, command, rng):
    attacker = battle["player"] if side == "PLAYER" else battle["enemy"]
    defender = battle["enemy"] if side == "PLAYER" else battle["player"]
    if _int(attacker.get("hp_current"), 0) <= 0:
        return
    can_act, condition_events = before_action(attacker, rng)
    _append_events(battle, condition_events, actor=attacker.get("entity_id"), target=attacker.get("entity_id"))
    if not can_act or _int(attacker.get("hp_current"), 0) <= 0:
        return

    move, synthetic = _prepare_move_action(battle, attacker, command.get("move_id"), rng)
    if not move:
        return
    battle["phase"] = "ACTION"
    _log(battle, "MOVE", f"{attacker['name']} usa {move['name']}.", actor=attacker["entity_id"], move_id=move["move_id"], pp_current=move.get("pp_current"))

    if _text(move.get("delivery")).upper() != "SELF":
        position_gate = position_move_gate(attacker, defender, move)
        if not position_gate.get("allowed"):
            _log(
                battle,
                "POSITION_BLOCKED_MOVE",
                _position_block_text(attacker, defender, position_gate),
                actor=attacker.get("entity_id"),
                target=defender.get("entity_id"),
                move_id=move.get("move_id"),
                position_status=position_gate.get("status"),
            )
            return
        set_incoming_reaction_context(defender, move)

    hit_accuracy = max(1, min(100, int(_int(move.get("accuracy"), 100) * accuracy_multiplier(attacker, defender))))
    if rng.randint(1, 100) > hit_accuracy:
        _log(battle, "MISS", "El ataque falla.", actor=attacker["entity_id"], target=defender["entity_id"], accuracy=hit_accuracy)
        return

    effectiveness_for_status = type_multiplier(move.get("pokemon_type"), defender.get("types"))
    if _text(move.get("damage_class")).upper() == "STATUS" and effectiveness_for_status == 0:
        _log(battle, "EFFECTIVENESS", "No tiene efecto.", target=defender["entity_id"], effectiveness=0)
        return

    damage, effectiveness, critical = _damage(attacker, defender, move, rng)
    if damage > 0:
        defender["hp_current"] = max(0, _int(defender.get("hp_current"), 0) - damage)
        _log(battle, "DAMAGE", f"{defender['name']} recibe {damage} de daño.", actor=attacker["entity_id"], target=defender["entity_id"], damage=damage, effectiveness=effectiveness, critical=critical)
        if effectiveness == 0:
            _log(battle, "EFFECTIVENESS", "No tiene efecto.", target=defender["entity_id"], effectiveness=0)
        elif effectiveness > 1:
            _log(battle, "EFFECTIVENESS", "Es muy eficaz.", target=defender["entity_id"], effectiveness=effectiveness)
        elif effectiveness < 1:
            _log(battle, "EFFECTIVENESS", "No es muy eficaz.", target=defender["entity_id"], effectiveness=effectiveness)
        if critical:
            _log(battle, "CRITICAL", "Golpe crítico.", target=defender["entity_id"])
    else:
        _log(battle, "STATUS_MOVE", f"{move['name']} altera la situación sin daño directo.", actor=attacker["entity_id"], target=defender["entity_id"])

    if effectiveness_for_status != 0 and _int(defender.get("hp_current"), 0) > 0:
        _append_events(battle, apply_move_effects(attacker, defender, move, rng), actor=attacker.get("entity_id"), target=defender.get("entity_id"))
    _queue_world_request(battle, attacker, defender, move, command)

    if synthetic and _int(attacker.get("hp_current"), 0) > 0:
        recoil = max(1, _int(attacker.get("hp_max"), 1) // 8)
        attacker["hp_current"] = max(0, _int(attacker.get("hp_current"), 0) - recoil)
        _log(battle, "RECOIL", f"{attacker['name']} recibe {recoil} de retroceso.", actor=attacker["entity_id"], damage=recoil)


def _execute_world_move_order(battle, side, command, rng):
    attacker = battle["player"] if side == "PLAYER" else battle["enemy"]
    if _int(attacker.get("hp_current"), 0) <= 0:
        return
    can_act, condition_events = before_action(attacker, rng)
    _append_events(battle, condition_events, actor=attacker.get("entity_id"), target=attacker.get("entity_id"))
    if not can_act or _int(attacker.get("hp_current"), 0) <= 0:
        return
    move, _synthetic = _prepare_move_action(battle, attacker, command.get("move_id"), rng)
    if not move:
        return
    if not bool(move.get("world_enabled")) or not _list(move.get("world_effects")):
        _log(battle, "WORLD_MOVE_REJECTED", f"{move['name']} no tiene uso ambiental autorizado.", actor=attacker["entity_id"], move_id=move["move_id"])
        return
    if rng.randint(1, 100) > max(1, min(100, _int(move.get("accuracy"), 100))):
        _log(battle, "WORLD_MOVE_MISS", f"{attacker['name']} no logra aplicar {move['name']} al entorno.", actor=attacker["entity_id"], move_id=move["move_id"])
        return
    battle["phase"] = "ACTION"
    _log(battle, "WORLD_MOVE_ORDER", f"{attacker['name']} usa {move['name']} sobre el entorno.", actor=attacker["entity_id"], move_id=move["move_id"], pp_current=move.get("pp_current"))
    _queue_world_request(battle, attacker, None, move, command)


def _capture(battle, command, rng):
    if str(battle.get("battle_kind") or "").upper() != "WILD" or not bool(battle["enemy"].get("wild")):
        _log(battle, "CAPTURE_BLOCKED", "No puedes capturar el Pokémon de otro entrenador.")
        return False
    enemy = battle["enemy"]
    missing = 1.0 - (_int(enemy.get("hp_current"), 0) / max(1, _int(enemy.get("hp_max"), 1)))
    status_bonus = 0.15 if _text(enemy.get("status")).upper() not in {"", "OK"} else 0.0
    ball_mult = max(0.5, min(3.0, _float(command.get("ball_multiplier"), 1.0)))
    chance = max(0.05, min(0.95, (0.20 + missing * 0.60 + status_bonus) * ball_mult))
    roll = rng.random()
    _log(battle, "CAPTURE_THROW", "Lanzas una Poké Ball.", chance=chance, roll=roll)
    if roll <= chance:
        battle["status"] = COMPLETE_STATUS
        battle["phase"] = "COMPLETE"
        battle["outcome"] = "CAPTURED"
        _log(battle, "CAPTURED", f"¡{enemy['name']} fue capturado!", target=enemy["entity_id"])
        return True
    _log(battle, "CAPTURE_FAILED", f"{enemy['name']} escapa de la Poké Ball.", target=enemy["entity_id"])
    return False


def _run(battle, rng):
    if str(battle.get("battle_kind") or "").upper() != "WILD":
        _log(battle, "RUN_BLOCKED", "No puedes abandonar así una batalla de entrenador.")
        return False
    p_speed = _speed(battle["player"])
    e_speed = _speed(battle["enemy"])
    chance = max(0.25, min(0.95, 0.55 + (p_speed - e_speed) / max(20.0, e_speed * 2.0)))
    if rng.random() <= chance:
        battle["status"] = COMPLETE_STATUS
        battle["phase"] = "COMPLETE"
        battle["outcome"] = "ESCAPED"
        _log(battle, "ESCAPED", "Escapas del encuentro.")
        return True
    _log(battle, "RUN_FAILED", "No logras escapar.")
    return False


def _execute_action(battle, row, rng):
    side = row["side"]
    action = _dict(row["action"])
    kind = _text(action.get("type")).upper()
    if battle.get("status") != ACTIVE_STATUS:
        return
    if kind == "MOVE":
        _execute_move(battle, side, action, rng)
    elif kind == "FREE_ORDER" and _text(action.get("move_id")):
        _execute_world_move_order(battle, side, action, rng)
    elif side == "PLAYER" and kind == "CAPTURE":
        _capture(battle, action, rng)
    elif side == "PLAYER" and kind == "RUN":
        _run(battle, rng)
    elif kind in {"SWITCH", "ITEM", "FREE_ORDER"}:
        if kind != "FREE_ORDER":
            _log(battle, "ACTION_RESERVED", f"{kind} se resuelve en el runtime autoritativo externo.", actor=side)
    else:
        _log(battle, "INVALID_ACTION", "Acción de batalla inválida.", actor=side)


def _end_check(battle):
    battle["phase"] = "END_CHECK"
    player_hp = _int(battle["player"].get("hp_current"), 0)
    enemy_hp = _int(battle["enemy"].get("hp_current"), 0)
    if enemy_hp <= 0 and player_hp <= 0:
        battle["status"] = COMPLETE_STATUS; battle["phase"] = "COMPLETE"; battle["outcome"] = "DRAW"
        _log(battle, "BATTLE_END", "Ambos Pokémon quedan fuera de combate.")
    elif enemy_hp <= 0:
        battle["status"] = COMPLETE_STATUS; battle["phase"] = "COMPLETE"; battle["outcome"] = "PLAYER_WIN"
        _log(battle, "BATTLE_END", f"{battle['enemy']['name']} queda fuera de combate.")
    elif player_hp <= 0:
        battle["status"] = COMPLETE_STATUS; battle["phase"] = "COMPLETE"; battle["outcome"] = "PLAYER_LOSS"
        _log(battle, "BATTLE_END", f"{battle['player']['name']} queda fuera de combate.")


def _apply_round_end(battle):
    if battle.get("status") != ACTIVE_STATUS:
        return
    battle["phase"] = "RESOLUTION"
    _append_events(battle, end_turn_effects(battle["player"], battle["enemy"]), actor=battle["player"].get("entity_id"))
    _append_events(battle, end_turn_effects(battle["enemy"], battle["player"]), actor=battle["enemy"].get("entity_id"))
    _end_check(battle)


def validate_player_action(battle, action):
    battle = _dict(battle)
    action = _dict(action)
    if _text(battle.get("status")) != ACTIVE_STATUS:
        return {"accepted": False, "status": "BATTLE_NOT_ACTIVE"}
    if _text(battle.get("phase")) != "COMMAND":
        return {"accepted": False, "status": "NOT_COMMAND_PHASE", "phase": battle.get("phase")}
    kind = _text(action.get("type")).upper()
    if kind not in ACTION_TYPES:
        return {"accepted": False, "status": "INVALID_ACTION_TYPE"}
    if kind == "MOVE" or (kind == "FREE_ORDER" and _text(action.get("move_id"))):
        move = move_by_id(battle.get("player") or {}, action.get("move_id"))
        if not move:
            return {"accepted": False, "status": "MOVE_NOT_KNOWN"}
        if _int(move.get("pp_current"), move.get("pp", 0)) <= 0:
            return {"accepted": False, "status": "NO_PP", "move_id": move.get("move_id")}
        if kind == "FREE_ORDER":
            if not _dict(action.get("world_target")):
                return {"accepted": False, "status": "WORLD_TARGET_REQUIRED"}
            if not bool(move.get("world_enabled")) or not _list(move.get("world_effects")):
                return {"accepted": False, "status": "MOVE_NOT_WORLD_ENABLED", "move_id": move.get("move_id")}
    return {"accepted": True, "status": "ACTION_VALID", "type": kind}


def resolve_player_action(battle, action, *, rng=None):
    """Resolve one complete 1v1 round and return a new battle snapshot."""
    rng = rng or random.SystemRandom()
    state = _clone(_dict(battle))
    validation = validate_player_action(state, action)
    if not validation.get("accepted"):
        return {"accepted": False, "status": validation.get("status"), "battle": state, "build": BATTLE_BUILD}

    state["pending_player_action"] = _clone(_dict(action))
    state["phase"] = "ORDER"
    enemy_action = _enemy_action(state, rng)
    order = _order_actions(state, action, enemy_action, rng)
    _log(state, "ORDER", "Las acciones quedan ordenadas.", order=[{"side": r["side"], "priority": r["priority"], "speed": r["speed"]} for r in order])

    for row in order:
        if state.get("status") != ACTIVE_STATUS:
            break
        _execute_action(state, row, rng)
        state["phase"] = "REACTION"
        _log(state, "REACTION_WINDOW", "Se comprueba reacción y efectos inmediatos.", actor=row["side"])
        _end_check(state)

    _apply_round_end(state)
    if state.get("status") == ACTIVE_STATUS:
        state["turn"] = _int(state.get("turn"), 1) + 1
        state["phase"] = "COMMAND"
    state["pending_player_action"] = None
    state["updated_at"] = int(time())
    return {"accepted": True, "status": "ROUND_RESOLVED", "battle": state, "enemy_action": enemy_action, "build": BATTLE_BUILD}


def public_battle_state(battle):
    state = _clone(_dict(battle))
    state.pop("pending_player_action", None)
    return state
