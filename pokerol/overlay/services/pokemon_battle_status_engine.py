"""Battle status/stage rules for POKEROL.

This layer is intentionally explicit and deterministic apart from the supplied RNG.
It owns major status, volatile effects and stat-stage arithmetic; the battle core
owns turn sequencing and HP authority.
"""

from copy import deepcopy

from services.pokemon_battle_position_engine import (
    position_accuracy_multiplier,
    position_speed_multiplier,
)


STATUS_BUILD = "0.2.0-status-position-runtime"
MAJOR_STATUSES = {"OK", "BURN", "POISON", "PARALYSIS", "SLEEP", "FREEZE"}
STAGE_KEYS = ("ATK", "DEF", "SPA", "SPD", "SPE", "ACC", "EVA")

# Backward-compatible effects for the first Kanto catalog. New authored moves can
# provide battle_effects directly and bypass this table.
DEFAULT_MOVE_EFFECTS = {
    "EMBER": [{"kind": "STATUS", "target": "ENEMY", "status": "BURN", "chance": 0.10}],
    "POISON-STING": [{"kind": "STATUS", "target": "ENEMY", "status": "POISON", "chance": 0.30}],
    "THUNDER-SHOCK": [{"kind": "STATUS", "target": "ENEMY", "status": "PARALYSIS", "chance": 0.10}],
    "THUNDER-WAVE": [{"kind": "STATUS", "target": "ENEMY", "status": "PARALYSIS", "chance": 1.00}],
    "GROWL": [{"kind": "STAGE", "target": "ENEMY", "stat": "ATK", "stages": -1, "chance": 1.00}],
    "TAIL-WHIP": [{"kind": "STAGE", "target": "ENEMY", "stat": "DEF", "stages": -1, "chance": 1.00}],
    "SAND-ATTACK": [{"kind": "STAGE", "target": "ENEMY", "stat": "ACC", "stages": -1, "chance": 1.00}],
    "SMOKESCREEN": [{"kind": "STAGE", "target": "ENEMY", "stat": "ACC", "stages": -1, "chance": 1.00}],
    "STRING-SHOT": [{"kind": "STAGE", "target": "ENEMY", "stat": "SPE", "stages": -2, "chance": 1.00}],
    "HARDEN": [{"kind": "STAGE", "target": "SELF", "stat": "DEF", "stages": 1, "chance": 1.00}],
    "LEECH-SEED": [{"kind": "VOLATILE", "target": "ENEMY", "status": "SEEDED", "chance": 1.00}],
    "CONFUSION": [{"kind": "VOLATILE", "target": "ENEMY", "status": "CONFUSED", "chance": 0.10}],
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


def normalize_battle_conditions(pokemon):
    """Return a mutable battle-ready Pokémon condition packet."""
    p = pokemon
    status = _text(p.get("status")).upper() or "OK"
    if status not in MAJOR_STATUSES:
        status = "OK"
    p["status"] = status
    stages = _dict(p.get("battle_stages"))
    p["battle_stages"] = {key: max(-6, min(6, _int(stages.get(key), 0))) for key in STAGE_KEYS}
    volatile = _dict(p.get("volatile_status"))
    p["volatile_status"] = {str(k).upper(): deepcopy(v) for k, v in volatile.items() if str(k).strip()}
    p["status_turns"] = max(0, _int(p.get("status_turns"), 0))
    return p


def stage_multiplier(stage):
    value = max(-6, min(6, _int(stage, 0)))
    return (2.0 + value) / 2.0 if value >= 0 else 2.0 / (2.0 - value)


def accuracy_multiplier(attacker, defender):
    a = _dict(_dict(attacker).get("battle_stages")).get("ACC", 0)
    e = _dict(_dict(defender).get("battle_stages")).get("EVA", 0)
    stage = stage_multiplier(_int(a, 0) - _int(e, 0))
    return max(0.20, min(3.0, stage * position_accuracy_multiplier(attacker, defender)))


def effective_stat(pokemon, stat):
    key = _text(stat).upper()
    base = max(1, _int(_dict(_dict(pokemon).get("stats")).get(key), 1))
    stage = _int(_dict(_dict(pokemon).get("battle_stages")).get(key), 0)
    value = base * stage_multiplier(stage)
    status = _text(_dict(pokemon).get("status")).upper()
    if key == "ATK" and status == "BURN":
        value *= 0.75
    if key == "SPE" and status == "PARALYSIS":
        value *= 0.50
    if key == "SPE":
        value *= position_speed_multiplier(pokemon)
    return max(1, int(value))


def authored_effects(move):
    explicit = [deepcopy(_dict(row)) for row in _list(_dict(move).get("battle_effects")) if _dict(row)]
    if explicit:
        return explicit
    return deepcopy(DEFAULT_MOVE_EFFECTS.get(_text(_dict(move).get("move_id")).upper(), []))


def _target_for(effect, attacker, defender):
    return attacker if _text(effect.get("target")).upper() == "SELF" else defender


def _effect_chance(effect):
    raw = _float(effect.get("chance"), 1.0)
    return max(0.0, min(1.0, raw if raw <= 1.0 else raw / 100.0))


def apply_move_effects(attacker, defender, move, rng):
    """Apply battle-only effects after a successful move and return log packets."""
    events = []
    for effect in authored_effects(move):
        if rng.random() > _effect_chance(effect):
            continue
        kind = _text(effect.get("kind")).upper()
        target = _target_for(effect, attacker, defender)
        target_name = _text(target.get("name") or target.get("species_name")) or "Pokémon"
        if kind == "STATUS":
            status = _text(effect.get("status")).upper()
            if status not in MAJOR_STATUSES or status == "OK":
                continue
            current = _text(target.get("status")).upper() or "OK"
            if current != "OK":
                events.append({"kind": "STATUS_BLOCKED", "text": f"{target_name} ya tiene un problema de estado.", "status": current})
                continue
            target["status"] = status
            if status == "SLEEP":
                target["status_turns"] = max(1, _int(effect.get("turns"), rng.randint(1, 3)))
            events.append({"kind": "STATUS_APPLIED", "text": f"{target_name} queda {status}.", "status": status})
        elif kind == "STAGE":
            stat = _text(effect.get("stat")).upper()
            if stat not in STAGE_KEYS:
                continue
            delta = max(-6, min(6, _int(effect.get("stages"), 0)))
            stages = _dict(target.get("battle_stages"))
            before = max(-6, min(6, _int(stages.get(stat), 0)))
            after = max(-6, min(6, before + delta))
            stages[stat] = after
            target["battle_stages"] = stages
            if after == before:
                events.append({"kind": "STAGE_LIMIT", "text": f"{target_name} no puede cambiar más {stat}.", "stat": stat, "stage": after})
            else:
                direction = "sube" if after > before else "baja"
                events.append({"kind": "STAGE_CHANGED", "text": f"{stat} de {target_name} {direction}.", "stat": stat, "stage": after})
        elif kind == "VOLATILE":
            status = _text(effect.get("status")).upper()
            if not status:
                continue
            volatile = _dict(target.get("volatile_status"))
            if status == "CONFUSED":
                volatile[status] = {"turns": max(1, _int(effect.get("turns"), rng.randint(2, 4)))}
            else:
                volatile[status] = deepcopy(effect.get("data") if isinstance(effect.get("data"), dict) else True)
            target["volatile_status"] = volatile
            events.append({"kind": "VOLATILE_APPLIED", "text": f"{target_name} queda afectado por {status}.", "status": status})
    return events


def before_action(pokemon, rng):
    """Return whether the Pokémon may act this turn and mutate transient counters."""
    normalize_battle_conditions(pokemon)
    name = _text(pokemon.get("name") or pokemon.get("species_name")) or "Pokémon"
    status = _text(pokemon.get("status")).upper()
    events = []
    if status == "SLEEP":
        turns = max(0, _int(pokemon.get("status_turns"), 0))
        if turns > 0:
            pokemon["status_turns"] = turns - 1
            events.append({"kind": "SLEEP", "text": f"{name} está dormido."})
            if turns - 1 <= 0:
                pokemon["status"] = "OK"
                events.append({"kind": "WAKE", "text": f"{name} se despierta."})
            return False, events
        pokemon["status"] = "OK"
    elif status == "FREEZE":
        if rng.random() < 0.20:
            pokemon["status"] = "OK"
            events.append({"kind": "THAW", "text": f"{name} se descongela."})
        else:
            events.append({"kind": "FREEZE", "text": f"{name} está congelado."})
            return False, events
    elif status == "PARALYSIS" and rng.random() < 0.25:
        events.append({"kind": "PARALYSIS", "text": f"{name} no puede moverse por la parálisis."})
        return False, events

    volatile = _dict(pokemon.get("volatile_status"))
    confused = _dict(volatile.get("CONFUSED"))
    if confused:
        turns = max(0, _int(confused.get("turns"), 0))
        if turns <= 1:
            volatile.pop("CONFUSED", None)
            pokemon["volatile_status"] = volatile
            events.append({"kind": "CONFUSION_END", "text": f"{name} deja de estar confundido."})
        else:
            confused["turns"] = turns - 1
            volatile["CONFUSED"] = confused
            pokemon["volatile_status"] = volatile
            if rng.random() < 0.33:
                damage = max(1, _int(pokemon.get("hp_max"), 1) // 12)
                pokemon["hp_current"] = max(0, _int(pokemon.get("hp_current"), 0) - damage)
                events.append({"kind": "CONFUSION_SELF_HIT", "text": f"{name} se golpea en su confusión y recibe {damage} de daño.", "damage": damage})
                return False, events
    return True, events


def end_turn_effects(pokemon, opponent=None):
    """Apply residual major/volatile effects. Returns events and optional drain amount."""
    normalize_battle_conditions(pokemon)
    name = _text(pokemon.get("name") or pokemon.get("species_name")) or "Pokémon"
    events = []
    hp_max = max(1, _int(pokemon.get("hp_max"), 1))
    status = _text(pokemon.get("status")).upper()
    if _int(pokemon.get("hp_current"), 0) > 0 and status in {"BURN", "POISON"}:
        divisor = 16 if status == "BURN" else 8
        damage = max(1, hp_max // divisor)
        pokemon["hp_current"] = max(0, _int(pokemon.get("hp_current"), 0) - damage)
        events.append({"kind": "STATUS_DAMAGE", "text": f"{name} recibe {damage} de daño por {status}.", "status": status, "damage": damage})

    volatile = _dict(pokemon.get("volatile_status"))
    if _int(pokemon.get("hp_current"), 0) > 0 and volatile.get("SEEDED") and opponent is not None:
        drain = max(1, hp_max // 8)
        actual = min(drain, _int(pokemon.get("hp_current"), 0))
        pokemon["hp_current"] = max(0, _int(pokemon.get("hp_current"), 0) - actual)
        opponent["hp_current"] = min(_int(opponent.get("hp_max"), 1), _int(opponent.get("hp_current"), 0) + actual)
        events.append({"kind": "LEECH_SEED", "text": f"Leech Seed drena {actual} HP de {name}.", "damage": actual})
    return events
