"""Server-authoritative Pokémon battle core for POKEROL.

The browser is presentation/input only. This module owns battle state, command
validation, ordering, hit checks, damage, basic capture/run resolution and the
battle log. World/terrain side-effects are exposed as requests for the World
Engine rather than being silently mutated here.
"""

from __future__ import annotations

import math
import random
from copy import deepcopy
from time import time
from uuid import uuid4


BATTLE_BUILD = "0.1.0-pokemon-authoritative-1v1"
PHASES = (
    "INTRO",
    "COMMAND",
    "ORDER",
    "ACTION",
    "REACTION",
    "RESOLUTION",
    "END_CHECK",
    "SWITCH",
    "COMPLETE",
)
ACTIVE_STATUS = "ACTIVE"
COMPLETE_STATUS = "COMPLETE"
ACTION_TYPES = {"MOVE", "CAPTURE", "RUN", "SWITCH", "ITEM", "FREE_ORDER"}

# Compact modern type chart. Missing pair = neutral.
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
    # Intentionally simple anime-RPG scaling: stable and readable, no hidden IV/EV layer.
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
    for raw in _list(p.get("moves") or p.get("resolved_moves")):
        move = _dict(raw)
        move_id = _text(move.get("move_id"))
        if not move_id:
            continue
        moves.append({
            "move_id": move_id,
            "name": _text(move.get("name")) or move_id,
            "pokemon_type": (_text(move.get("pokemon_type") or move.get("type")) or "Normal").upper(),
            "damage_class": (_text(move.get("damage_class")) or "PHYSICAL").upper(),
            "power": max(0, _int(move.get("power"), 0)),
            "accuracy": max(1, min(100, _int(move.get("accuracy"), 100))),
            "priority": _int(move.get("priority"), 0),
            "pp": max(0, _int(move.get("pp"), 20)),
            "world_enabled": bool(move.get("world_enabled", False)),
            "world_effects": [str(v) for v in _list(move.get("world_effects")) if str(v)],
            "materials": [str(v) for v in _list(move.get("materials")) if str(v)],
            "delivery": _text(move.get("delivery")),
            "requirements": _dict(move.get("requirements")),
        })
    return {
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
        "side": str(side or "PLAYER").upper(),
        "moves": moves,
        "sprite": _sprite(p),
        "trainer": _dict(p.get("trainer")),
        "wild": bool(p.get("wild", str(side).upper() == "ENEMY")),
        "battle_tags": [str(v) for v in _list(p.get("battle_tags")) if str(v)],
    }


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
    if len(battle["log"]) > 80:
        battle["log"] = battle["log"][-80:]
    return row


def move_by_id(pokemon, move_id):
    wanted = _text(move_id).upper()
    for move in _list(_dict(pokemon).get("moves")):
        row = _dict(move)
        if _text(row.get("move_id")).upper() == wanted:
            return row
    return None


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
    a_stats = _dict(attacker.get("stats")); d_stats = _dict(defender.get("stats"))
    attack = max(1, _int(a_stats.get("ATK" if damage_class == "PHYSICAL" else "SPA"), 1))
    defense = max(1, _int(d_stats.get("DEF" if damage_class == "PHYSICAL" else "SPD"), 1))
    level = max(1, _int(attacker.get("level"), 1))
    base = math.floor((math.floor((2 * level) / 5) + 2) * power * attack / defense / 50) + 2
    stab = 1.5 if _text(move.get("pokemon_type")).upper() in _types(attacker.get("types")) else 1.0
    effectiveness = type_multiplier(move.get("pokemon_type"), defender.get("types"))
    critical = rng.random() < (1.0 / 16.0)
    modifier = stab * effectiveness * (1.5 if critical else 1.0) * rng.uniform(0.85, 1.0)
    return max(0, math.floor(base * modifier)), effectiveness, critical


def _enemy_action(battle, rng):
    enemy = _dict(battle.get("enemy"))
    moves = [m for m in _list(enemy.get("moves")) if _dict(m)]
    if not moves:
        return {"type": "MOVE", "move_id": "STRUGGLE"}
    damaging = [m for m in moves if _int(_dict(m).get("power"), 0) > 0]
    pool = damaging or moves
    move = _dict(rng.choice(pool))
    return {"type": "MOVE", "move_id": _text(move.get("move_id"))}


def _action_priority(action, pokemon):
    kind = _text(_dict(action).get("type")).upper()
    if kind in {"CAPTURE", "SWITCH", "ITEM", "RUN"}:
        return 6
    if kind == "MOVE":
        move = move_by_id(pokemon, _dict(action).get("move_id")) or {}
        return _int(_dict(move).get("priority"), 0)
    return 0


def _speed(pokemon):
    return max(1, _int(_dict(_dict(pokemon).get("stats")).get("SPE"), 1))


def _order_actions(battle, player_action, enemy_action, rng):
    rows = [
        {"side": "PLAYER", "action": _dict(player_action), "pokemon": _dict(battle.get("player"))},
        {"side": "ENEMY", "action": _dict(enemy_action), "pokemon": _dict(battle.get("enemy"))},
    ]
    for row in rows:
        row["priority"] = _action_priority(row["action"], row["pokemon"])
        row["speed"] = _speed(row["pokemon"])
        row["tie"] = rng.random()
    rows.sort(key=lambda r: (r["priority"], r["speed"], r["tie"]), reverse=True)
    return rows


def _queue_world_request(battle, actor, target, move, command):
    move = _dict(move)
    if not bool(move.get("world_enabled")) or not _list(move.get("world_effects")):
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
        "world_target": _clone(_dict(_dict(command).get("world_target"))),
        "status": "PENDING_WORLD_RESOLUTION",
    })


def _execute_move(battle, side, command, rng):
    attacker = battle["player"] if side == "PLAYER" else battle["enemy"]
    defender = battle["enemy"] if side == "PLAYER" else battle["player"]
    if _int(attacker.get("hp_current"), 0) <= 0:
        return
    move = move_by_id(attacker, command.get("move_id"))
    if not move:
        _log(battle, "INVALID_MOVE", f"{attacker['name']} no conoce ese movimiento.", actor=attacker["entity_id"])
        return
    battle["phase"] = "ACTION"
    _log(battle, "MOVE", f"{attacker['name']} usa {move['name']}.", actor=attacker["entity_id"], move_id=move["move_id"])
    if rng.randint(1, 100) > max(1, _int(move.get("accuracy"), 100)):
        _log(battle, "MISS", "El ataque falla.", actor=attacker["entity_id"], target=defender["entity_id"])
        return
    damage, effectiveness, critical = _damage(attacker, defender, move, rng)
    if damage > 0:
        defender["hp_current"] = max(0, _int(defender.get("hp_current"), 0) - damage)
        text = f"{defender['name']} recibe {damage} de daño."
        _log(battle, "DAMAGE", text, actor=attacker["entity_id"], target=defender["entity_id"], damage=damage, effectiveness=effectiveness, critical=critical)
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
    _queue_world_request(battle, attacker, defender, move, command)


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
    p_speed = _speed(battle["player"]); e_speed = _speed(battle["enemy"])
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
    elif side == "PLAYER" and kind == "CAPTURE":
        _capture(battle, action, rng)
    elif side == "PLAYER" and kind == "RUN":
        _run(battle, rng)
    elif kind in {"SWITCH", "ITEM", "FREE_ORDER"}:
        _log(battle, "ACTION_RESERVED", f"{kind} está en el contrato de batalla pero requiere party/inventory/free-order runtime.", actor=side)
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


def validate_player_action(battle, action):
    battle = _dict(battle); action = _dict(action)
    if _text(battle.get("status")) != ACTIVE_STATUS:
        return {"accepted": False, "status": "BATTLE_NOT_ACTIVE"}
    if _text(battle.get("phase")) != "COMMAND":
        return {"accepted": False, "status": "NOT_COMMAND_PHASE", "phase": battle.get("phase")}
    kind = _text(action.get("type")).upper()
    if kind not in ACTION_TYPES:
        return {"accepted": False, "status": "INVALID_ACTION_TYPE"}
    if kind == "MOVE" and not move_by_id(_dict(battle.get("player")), action.get("move_id")):
        return {"accepted": False, "status": "MOVE_NOT_KNOWN"}
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
        _log(state, "REACTION_WINDOW", "Se comprueba si la acción provoca una reacción o efecto inmediato.", actor=row["side"])
        state["phase"] = "RESOLUTION"
        _end_check(state)

    if state.get("status") == ACTIVE_STATUS:
        state["turn"] = _int(state.get("turn"), 1) + 1
        state["phase"] = "COMMAND"
    state["pending_player_action"] = None
    state["updated_at"] = int(time())
    return {"accepted": True, "status": "ROUND_RESOLVED", "battle": state, "enemy_action": enemy_action, "build": BATTLE_BUILD}


def public_battle_state(battle):
    """Packet safe for the webclient. Keeps authoritative internals server-side."""
    state = _clone(_dict(battle))
    state.pop("pending_player_action", None)
    return state
