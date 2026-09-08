"""Resolve direct-move and position-change rounds with contextual Tsubasa reactions."""

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
from services.pokemon_battle_reaction_window_engine import build_window
from services.pokemon_battle_status_engine import before_action
from services.pokemon_battle_tactical_action_engine import (
    enemy_action_position_aware,
    execute_row_position_aware,
    move_reach_gate,
)


TACTICAL_ROUND_BUILD = "0.3.0-contextual-reaction-window"


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
    state.pop("pending_round_resume", None)
    state.pop("pending_reaction_window", None)
    state["updated_at"] = int(time())


def _declare_wego_round(state, player_action, rng):
    enemy_action = enemy_action_position_aware(state, rng)
    order = _order_actions(state, player_action, enemy_action, rng)
    declaration = {
        "mode": "WEGO",
        "turn": _int(state.get("turn"), 1),
        "player_action": _clone(player_action),
        "enemy_action": _clone(enemy_action),
        "resolution_order": [
            {"side": row["side"], "priority": row["priority"], "speed": row["speed"]}
            for row in order
        ],
    }
    state["round_declaration"] = _clone(declaration)
    state["last_round_declaration"] = _clone(declaration)
    _log(
        state,
        "WEGO_DECLARATION",
        "Ambos bandos declaran su intención. Después se revelan y resuelven según prioridad, velocidad y posición.",
        player_action=_clone(player_action),
        enemy_action=_clone(enemy_action),
        order=_clone(declaration["resolution_order"]),
    )
    return enemy_action, order


def _serial_order(order):
    return [
        {
            "side": _text(_dict(row).get("side")).upper(),
            "action": _clone(_dict(_dict(row).get("action"))),
            "priority": _dict(row).get("priority"),
            "speed": _dict(row).get("speed"),
            "tie": _dict(row).get("tie"),
        }
        for row in _list(order)
    ]


def _can_open_reaction_window(state, row):
    row = _dict(row)
    if _text(row.get("side")).upper() != "ENEMY":
        return False
    action = _dict(row.get("action"))
    if _text(action.get("type")).upper() != "MOVE":
        return False
    if _int(_dict(state.get("player")).get("hp_current"), 0) <= 0:
        return False
    gate = move_reach_gate(state, "ENEMY", action)
    return bool(gate.get("allowed"))


def _pause_for_reaction(state, order, index, player_action, position_action, verified_target):
    row = _dict(order[index])
    if not _can_open_reaction_window(state, row):
        return None
    window = build_window(state, _dict(row.get("action")))
    if not window:
        return None
    state["phase"] = "REACTION"
    state["pending_reaction_window"] = _clone(window)
    state["pending_round_resume"] = {
        "order": _serial_order(order),
        "next_index": int(index),
        "player_action": _clone(player_action),
        "position_action": _text(position_action),
        "verified_target": _clone(verified_target) if verified_target else None,
    }
    state["updated_at"] = int(time())
    _log(
        state,
        "REACTION_WINDOW_OPEN",
        f"{window.get('attacker_name') or 'El rival'} inicia {window.get('move_name') or 'un ataque'}. ¡Ventana de reacción!",
        actor=_dict(state.get("enemy")).get("entity_id"),
        target=_dict(state.get("player")).get("entity_id"),
        move_id=window.get("move_id"),
        reaction_window_id=window.get("window_id"),
    )
    return window


def _run_order(state, order, *, start_index, player_action, position_action, verified_target, rng, skip_window_index=None):
    for index in range(max(0, int(start_index)), len(order)):
        if state.get("status") != ACTIVE_STATUS:
            break
        row = _dict(order[index])
        if index != skip_window_index:
            window = _pause_for_reaction(state, order, index, player_action, position_action, verified_target)
            if window:
                return {"paused": True, "window": window}

        if _text(row.get("side")).upper() == "PLAYER" and position_action:
            _position_player_row(state, player_action, verified_target, rng)
        else:
            execute_row_position_aware(state, row, rng)
        _end_check(state)

    _round_finish(state)
    state.pop("round_declaration", None)
    return {"paused": False}


def resolve_tactical_player_action(actor, battle, action, *, rng=None):
    """Resolve a tactical action, pausing only when an enemy attack opens a real reaction window."""
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
    enemy_action, order = _declare_wego_round(state, action, rng)
    run = _run_order(
        state,
        order,
        start_index=0,
        player_action=action,
        position_action=position_action,
        verified_target=verified_target,
        rng=rng,
    )
    if run.get("paused"):
        return {
            "accepted": True,
            "status": "REACTION_WINDOW_OPEN",
            "battle": state,
            "enemy_action": enemy_action,
            "reaction_window": _clone(run.get("window")),
            "round_declaration": _clone(state.get("last_round_declaration")),
            "build": TACTICAL_ROUND_BUILD,
            "engine_build": BATTLE_BUILD,
        }

    return {
        "accepted": True,
        "status": "TACTICAL_WEGO_ROUND_RESOLVED",
        "battle": state,
        "enemy_action": enemy_action,
        "round_declaration": _clone(state.get("last_round_declaration")),
        "build": TACTICAL_ROUND_BUILD,
        "engine_build": BATTLE_BUILD,
    }


def resume_tactical_reaction(battle, *, rng=None):
    """Continue the exact paused round after the reaction choice has been applied."""
    rng = rng or random.SystemRandom()
    state = _clone(_dict(battle))
    resume = _dict(state.get("pending_round_resume"))
    window = _dict(state.get("pending_reaction_window"))
    if not resume or not window:
        return {"accepted": False, "status": "NO_REACTION_WINDOW", "battle": state, "build": TACTICAL_ROUND_BUILD}
    if _text(window.get("status")).upper() == "OPEN":
        return {"accepted": False, "status": "REACTION_WINDOW_UNANSWERED", "battle": state, "build": TACTICAL_ROUND_BUILD}

    order = [_dict(row) for row in _list(resume.get("order"))]
    next_index = max(0, _int(resume.get("next_index"), 0))
    player_action = _dict(resume.get("player_action"))
    position_action = _text(resume.get("position_action")).upper()
    verified_target = _dict(resume.get("verified_target")) or None

    choice = _text(window.get("choice")).upper() or "PASS"
    if choice == "PASS":
        _log(
            state,
            "REACTION_PASSED",
            f"{_dict(state.get('player')).get('name') or 'El Pokémon'} no reacciona a tiempo.",
            target=_dict(state.get("player")).get("entity_id"),
            reaction_window_id=window.get("window_id"),
        )
    else:
        _log(
            state,
            "REACTION_CHOSEN",
            f"{_dict(state.get('player')).get('name') or 'El Pokémon'} intenta {choice.lower()}.",
            target=_dict(state.get("player")).get("entity_id"),
            reaction=choice,
            reaction_window_id=window.get("window_id"),
        )

    run = _run_order(
        state,
        order,
        start_index=next_index,
        player_action=player_action,
        position_action=position_action,
        verified_target=verified_target,
        rng=rng,
        skip_window_index=next_index,
    )
    if run.get("paused"):
        return {
            "accepted": True,
            "status": "REACTION_WINDOW_OPEN",
            "battle": state,
            "reaction_window": _clone(run.get("window")),
            "build": TACTICAL_ROUND_BUILD,
            "engine_build": BATTLE_BUILD,
        }
    return {
        "accepted": True,
        "status": "TACTICAL_WEGO_ROUND_RESOLVED",
        "battle": state,
        "build": TACTICAL_ROUND_BUILD,
        "engine_build": BATTLE_BUILD,
    }
