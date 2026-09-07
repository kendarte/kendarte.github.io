"""Position-aware execution helpers layered over the pure Pokémon battle core."""

from services.pokemon_battle_engine import (
    _append_events,
    _enemy_action,
    _execute_action,
    _log,
    _prepare_move_action,
    move_by_id,
)
from services.pokemon_battle_position_engine import normalized_position, position_move_gate
from services.pokemon_battle_reaction_engine import (
    clear_incoming_reaction_context,
    set_incoming_reaction_context,
    settle_incoming_attack_reaction,
)
from services.pokemon_battle_spatial_resolver import resolve_attack_path
from services.pokemon_battle_status_engine import before_action
from services.pokemon_move_capability_engine import canonical_trajectory, move_combat_profile


TACTICAL_ACTION_BUILD = "0.4.0-tag-trajectory-cover"


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


def _combatants(state, side):
    if _text(side).upper() == "PLAYER":
        return _dict(state.get("player")), _dict(state.get("enemy"))
    return _dict(state.get("enemy")), _dict(state.get("player"))


def _cover_obstacle(defender):
    """Translate authoritative battle_position.cover into the generic path resolver.

    Old saves may only have rating/name; newer authored targets may also carry tags.
    Low rating is treated as low cover, not as a fabricated physical object type.
    """
    cover = _dict(normalized_position(defender).get("cover"))
    if not cover:
        return None
    tags = {str(v).strip().upper() for v in _list(cover.get("tags")) if str(v).strip()}
    tags.add("COVER")
    rating = _float(cover.get("rating"), 0.20)
    if rating <= 0.25:
        tags.add("LOW_OBSTACLE")
    elif rating >= 0.42:
        tags.add("HIGH_OBSTACLE")
    if bool(cover.get("fragile")):
        tags.add("FRAGILE_COVER")
    return {
        "object_id": cover.get("object_id") or cover.get("target_id"),
        "dbref": cover.get("dbref"),
        "name": cover.get("name") or "cobertura",
        "tags": sorted(tags),
    }


def move_reach_gate(state, side, action):
    action = _dict(action)
    if _text(action.get("type")).upper() != "MOVE":
        return {"allowed": True, "status": "NOT_DIRECT_MOVE", "build": TACTICAL_ACTION_BUILD}
    attacker, defender = _combatants(state, side)
    move = move_by_id(attacker, action.get("move_id"))
    if not move:
        return {"allowed": False, "status": "MOVE_NOT_KNOWN", "build": TACTICAL_ACTION_BUILD}

    profile = move_combat_profile(move)
    if canonical_trajectory(move) == "SELF":
        return {"allowed": True, "status": "SELF_MOVE", "combat_profile": profile, "build": TACTICAL_ACTION_BUILD}

    position_gate = position_move_gate(attacker, defender, move)
    if not position_gate.get("allowed"):
        return {**position_gate, "move_id": move.get("move_id"), "combat_profile": profile}

    obstacle = _cover_obstacle(defender)
    path = resolve_attack_path(
        move,
        obstacles=[obstacle] if obstacle else [],
        target={"tags": ["AIRBORNE"] if normalized_position(defender).get("stance") == "AIR" else []},
        environment={"target_ground_contact": normalized_position(defender).get("stance") != "AIR"},
    )
    if not path.get("clear"):
        return {
            "allowed": False,
            "status": path.get("status") or "BLOCKED_BY_COVER",
            "move_id": move.get("move_id"),
            "combat_profile": profile,
            "spatial_path": path,
            "build": TACTICAL_ACTION_BUILD,
        }
    return {
        "allowed": True,
        "status": path.get("status") or "POSITION_REACH_VALID",
        "move_id": move.get("move_id"),
        "combat_profile": profile,
        "spatial_path": path,
        "build": TACTICAL_ACTION_BUILD,
    }


def enemy_action_position_aware(state, rng):
    """Prefer enemy moves that can physically reach the current player position."""
    enemy = _dict(state.get("enemy"))
    reachable = []
    for move in _list(enemy.get("moves")):
        move = _dict(move)
        if _int(move.get("pp_current"), move.get("pp", 0)) <= 0:
            continue
        action = {"type": "MOVE", "move_id": move.get("move_id")}
        if move_reach_gate(state, "ENEMY", action).get("allowed"):
            reachable.append(move)
    if not reachable:
        return _enemy_action(state, rng)
    damaging = [move for move in reachable if _int(move.get("power"), 0) > 0]
    chosen = rng.choice(damaging or reachable)
    return {"type": "MOVE", "move_id": _text(chosen.get("move_id"))}


def _execute_blocked_move(state, side, action, rng, gate):
    attacker, defender = _combatants(state, side)
    if _int(attacker.get("hp_current"), 0) <= 0:
        return {"executed": False, "status": "ATTACKER_FAINTED"}
    can_act, condition_events = before_action(attacker, rng)
    _append_events(state, condition_events, actor=attacker.get("entity_id"), target=attacker.get("entity_id"))
    if not can_act or _int(attacker.get("hp_current"), 0) <= 0:
        return {"executed": False, "status": "CONDITION_BLOCKED"}
    move, _synthetic = _prepare_move_action(state, attacker, action.get("move_id"), rng)
    if not move:
        return {"executed": False, "status": "MOVE_PREPARE_FAILED"}
    state["phase"] = "ACTION"
    _log(
        state,
        "MOVE",
        f"{attacker['name']} usa {move['name']}.",
        actor=attacker.get("entity_id"),
        move_id=move.get("move_id"),
        pp_current=move.get("pp_current"),
    )
    status = _text(gate.get("status")) or "TARGET_OUT_OF_REACH"
    blocking = _dict(_dict(gate.get("spatial_path")).get("blocking_object"))
    if status in {"BLOCKED_BY_COVER", "BLOCKED_OVERHEAD"}:
        text = f"{blocking.get('name') or 'La cobertura'} intercepta la trayectoria de {move.get('name') or 'el ataque'}."
    elif status == "TARGET_OUT_OF_REACH_AIR":
        text = f"{defender.get('name') or 'El objetivo'} está fuera del alcance: se encuentra en el aire."
    elif status == "TARGET_OUT_OF_REACH_ELEVATED":
        text = f"{defender.get('name') or 'El objetivo'} está fuera del alcance desde esa altura."
    elif status == "ATTACKER_NOT_GROUNDED":
        text = f"{attacker.get('name') or 'El Pokémon'} necesita apoyo en el suelo para ejecutar ese movimiento."
    elif status == "WATER_POSITION_REQUIRED":
        text = "Ese movimiento necesita una posición vinculada al agua."
    else:
        text = "La posición actual impide que el movimiento alcance el objetivo."
    _log(
        state,
        "POSITION_BLOCKED_MOVE",
        text,
        actor=attacker.get("entity_id"),
        target=defender.get("entity_id"),
        move_id=move.get("move_id"),
        position_status=status,
        spatial_path=_dict(gate.get("spatial_path")),
    )
    return {"executed": True, "status": status, "blocked": True, "spatial_path": gate.get("spatial_path")}


def execute_row_position_aware(state, row, rng):
    """Execute one ordered row with reach, trajectory/cover and one-shot defensive reactions."""
    row = _dict(row)
    action = _dict(row.get("action"))
    side = _text(row.get("side")).upper()
    if _text(action.get("type")).upper() == "MOVE":
        gate = move_reach_gate(state, side, action)
        if not gate.get("allowed"):
            return _execute_blocked_move(state, side, action, rng, gate)
        attacker, defender = _combatants(state, side)
        incoming_move = move_by_id(attacker, action.get("move_id"))
        if incoming_move and canonical_trajectory(incoming_move) != "SELF":
            set_incoming_reaction_context(defender, incoming_move)
        log_start = len(_list(state.get("log")))
        _execute_action(state, row, rng)
        defender_side = "ENEMY" if side == "PLAYER" else "PLAYER"
        reaction = settle_incoming_attack_reaction(state, defender_side, log_start)
        if not reaction.get("consumed"):
            clear_incoming_reaction_context(defender)
        return {
            "executed": True,
            "status": "CORE_ACTION_EXECUTED",
            "blocked": False,
            "reaction": reaction,
            "spatial_path": gate.get("spatial_path"),
            "combat_profile": gate.get("combat_profile"),
        }
    _execute_action(state, row, rng)
    return {"executed": True, "status": "CORE_ACTION_EXECUTED", "blocked": False}
