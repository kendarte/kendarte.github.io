"""Resolve direct-move and position-change rounds with anime spatial rules."""

import random
from copy import deepcopy
from time import time

from services.pokemon_battle_engine import (
    ACTIVE_STATUS,
    BATTLE_BUILD,
    _append_events,
    _apply_round_end,
    _end_check,
    _log,
    _order_actions,
    _prepare_move_action,
    validate_player_action,
)
from services.pokemon_battle_position_engine import (
    apply_verified_position,
    resolve_position_target,
)
from services.pokemon_battle_status_engine import before_action
from services.pokemon_battle_tactical_action_engine import (
    enemy_action_position_aware,
    execute_row_position_aware,
    move_reach_gate,
)


TACTICAL_ROUND_BUILD = "0.1.0-anime-position-round"


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


def _clone(value):
    return deepcopy(value)


def _position_player_row(state, action, target, rng):
    player = _dict(state.get("player"))
    if _int(player.get("hp_current"), 0) <= 0:
        return {"executed": False, "status": "PLAYER_FAINTED"}

    can_act, condition_events = before_action(player, rng)
    _append_events(
        state,
        condition_events,
        actor=player.get("entity_id"),
        target=player.get("entity_id"),
    )
    if not can_act or _int(player.get("hp_current"), 0) <= 0:
        return {"executed": False, "status": "CONDITION_BLOCKED"}

    method_move_id = _text(_dict(action).get("method_move_id"))
    if method_move_id:
        move, _synthetic = _prepare_move_action(state, player, method_move_id, rng)
        if not move:
            return {"executed": False, "status": "POSITION_METHOD_MOVE_FAILED"}
        state["phase"] = "ACTION"
        _log(
            state,
            "POSITION_MOVE",
            f"{player.get('name') or 'Pokémon'} usa {move.get('name') or method_move_id} para cambiar de posición.",
            actor=player.get("entity_id"),
            move_id=move.get("move_id"),
            pp_current=move.get("pp_current"),
        )

    result = apply_verified_position(player, target)
    if result.get("applied"):
        _log(
            state,
            "POSITION_CHANGED",
            result.get("text") or "La posición cambia.",
            actor=player.get("entity_id"),
            position_action=result.get("action"),
            position=result.get("position"),
            target_id=_dict(target).get("target_id"),
            method_move_id=method_move_id or None,
        )
    return result


def _round_finish(state):
    _apply_round_end(state)
    if state.get("status") == ACTIVE_STATUS:
        state["turn"] = _int(state.get("turn"), 1) + 1
        state["phase"] = "COMMAND"
    state["pending_player_action"] = None
    state["updated_at"] = int(time())


def _ordered_rows(state, player_action, rng):
    enemy_action = enemy_action_position_aware(state, rng)
    order = _order_actions(state, player_action, enemy_action, rng)
    _log(
        state,
        "ORDER",
        "Las acciones quedan ordenadas según prioridad, velocidad y posición.",
        order=[
            {"side": row["side"], "priority": row["priority"], "speed": row["speed"]}
            for row in order
        ],
    )
    return enemy_action, order


def resolve_tactical_player_action(actor, battle, action, *, rng=None):
    """Resolve MOVE or FREE_ORDER/position_action using positional combat rules."""
    rng = rng or random.SystemRandom()
    state = _clone(_dict(battle))
    action = _dict(action)
    kind = _text(action.get("type")).upper()
    position_action = _text(action.get("position_action")).upper()

    validation = validate_player_action(state, action)
    if not validation.get("accepted"):
        return {
            "accepted": False,
            "status": validation.get("status"),
            "battle": state,
            "build": TACTICAL_ROUND_BUILD,
            "engine_build": BATTLE_BUILD,
        }

    if kind == "MOVE":
        reach = move_reach_gate(state, "PLAYER", action)
        if not reach.get("allowed"):
            return {
                "accepted": False,
                "status": reach.get("status") or "TARGET_OUT_OF_REACH",
                "battle": state,
                "position_gate": reach,
                "build": TACTICAL_ROUND_BUILD,
                "engine_build": BATTLE_BUILD,
            }
        verified_target = None
    elif kind == "FREE_ORDER" and position_action:
        verified_target = resolve_position_target(actor, state, action, side="PLAYER")
        if not verified_target:
            return {
                "accepted": False,
                "status": "POSITION_TARGET_NOT_AUTHORIZED",
                "battle": state,
                "build": TACTICAL_ROUND_BUILD,
                "engine_build": BATTLE_BUILD,
            }
    else:
        return {
            "accepted": False,
            "status": "NOT_TACTICAL_ACTION",
            "battle": state,
            "build": TACTICAL_ROUND_BUILD,
        }

    state["pending_player_action"] = _clone(action)
    state["phase"] = "ORDER"
    enemy_action, order = _ordered_rows(state, action, rng)

    for row in order:
        if state.get("status") != ACTIVE_STATUS:
            break
        if _text(row.get("side")).upper() == "PLAYER" and position_action:
            _position_player_row(state, action, verified_target, rng)
        else:
            execute_row_position_aware(state, row, rng)
        if state.get("status") != ACTIVE_STATUS:
            break
        state["phase"] = "REACTION"
        _log(
            state,
            "REACTION_WINDOW",
            "Se comprueba alcance, cobertura y efectos inmediatos.",
            actor=row.get("side"),
        )
        _end_check(state)

    _round_finish(state)
    return {
        "accepted": True,
        "status": "TACTICAL_ROUND_RESOLVED",
        "battle": state,
        "enemy_action": enemy_action,
        "build": TACTICAL_ROUND_BUILD,
        "engine_build": BATTLE_BUILD,
    }
