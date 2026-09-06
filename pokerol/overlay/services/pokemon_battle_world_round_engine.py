"""Resolve environment-targeted battle rounds at exact initiative timing.

This orchestrator reuses the pure battle core ordering/action primitives. Only the
world-target action pauses the round to execute authoritative Evennia physics and
translate shared-medium impacts back into Pokémon HP/status before the next actor.
"""

import random
from copy import deepcopy
from time import time

from services.pokemon_battle_engine import (
    ACTIVE_STATUS,
    BATTLE_BUILD,
    _apply_round_end,
    _end_check,
    _enemy_action,
    _execute_action,
    _log,
    _order_actions,
    move_by_id,
    validate_player_action,
)
from services.pokemon_battle_environment_engine import execute_battle_environment_request
from services.pokemon_battle_physics_impact_engine import apply_world_physics_to_battle


WORLD_ROUND_BUILD = "0.1.0-initiative-world-resolution"


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


def _append_impact_events(state, impact):
    for hit in _list(_dict(impact).get("impacts")):
        hit = _dict(hit)
        for event in _list(hit.get("events")):
            event = _dict(event)
            _log(
                state,
                _text(event.get("kind")) or "WORLD_BATTLE_IMPACT",
                _text(event.get("text")) or "El entorno afecta al combate.",
                target=hit.get("entity_id"),
                medium_id=hit.get("medium_id"),
                damage=event.get("damage"),
                effectiveness=event.get("effectiveness"),
                critical=event.get("critical"),
            )


def _resolve_new_world_requests(actor, state, previous_count):
    requests = _list(state.get("world_requests"))
    player = _dict(state.get("player"))
    changed = False
    for index in range(max(0, previous_count), len(requests)):
        request = _dict(requests[index])
        if _text(request.get("status")) != "PENDING_WORLD_RESOLUTION":
            continue
        if _text(request.get("actor_entity_id")) != _text(player.get("entity_id")):
            request["status"] = "WORLD_ACTOR_NOT_SUPPORTED"
            request["resolution"] = {"executed": False, "status": "WORLD_ACTOR_NOT_SUPPORTED"}
            requests[index] = request
            changed = True
            continue
        move = move_by_id(player, request.get("move_id"))
        if not move:
            request["status"] = "WORLD_MOVE_MISSING"
            request["resolution"] = {"executed": False, "status": "WORLD_MOVE_MISSING"}
            requests[index] = request
            changed = True
            continue

        world_result = execute_battle_environment_request(actor, player, move, request)
        executed = bool(world_result.get("executed"))
        impact = apply_world_physics_to_battle(state, move, world_result)
        request["status"] = "WORLD_EXECUTED" if executed else "WORLD_REJECTED"
        request["resolution"] = {
            "executed": executed,
            "status": world_result.get("status"),
            "target_dbref": world_result.get("target_dbref"),
            "target_object_id": world_result.get("target_object_id"),
            "target_name": world_result.get("target_name"),
            "target_water_body_id": world_result.get("target_water_body_id"),
            "target_materials": _clone(_list(world_result.get("target_materials"))),
            "persisted_target_state": _clone(_dict(world_result.get("persisted_target_state"))),
            "events": _clone(_list(world_result.get("events"))),
            "area_impacts": _clone(_list(world_result.get("area_impacts"))),
            "persisted_area_impacts": _clone(_list(world_result.get("persisted_area_impacts"))),
            "battle_impact": _clone(impact),
        }
        target_name = _text(world_result.get("target_name")) or _text(_dict(request.get("world_target")).get("name")) or "el entorno"
        if executed:
            _log(
                state,
                "WORLD_EFFECT",
                f"El efecto físico alcanza {target_name}.",
                request_id=request.get("request_id"),
                world_status=world_result.get("status"),
                medium_id=world_result.get("target_water_body_id"),
            )
            _append_impact_events(state, impact)
        else:
            _log(
                state,
                "WORLD_EFFECT_REJECTED",
                f"La interacción con {target_name} no produce un efecto físico válido.",
                request_id=request.get("request_id"),
                world_status=world_result.get("status"),
            )
        requests[index] = request
        changed = True
        _end_check(state)
    if changed:
        state["world_requests"] = requests[-80:]
        state["last_world_resolution"] = _clone(_dict(requests[-1].get("resolution"))) if requests else None
    return changed


def resolve_environment_player_action(actor, battle, action, *, rng=None):
    """Resolve one player environment order with physics at its actual initiative."""
    rng = rng or random.SystemRandom()
    state = _clone(_dict(battle))
    action = _dict(action)
    validation = validate_player_action(state, action)
    if not validation.get("accepted"):
        return {
            "accepted": False,
            "status": validation.get("status"),
            "battle": state,
            "build": WORLD_ROUND_BUILD,
            "engine_build": BATTLE_BUILD,
        }

    if _text(action.get("type")).upper() != "FREE_ORDER" or not _text(action.get("move_id")):
        return {
            "accepted": False,
            "status": "NOT_ENVIRONMENT_MOVE_ORDER",
            "battle": state,
            "build": WORLD_ROUND_BUILD,
        }

    state["pending_player_action"] = _clone(action)
    state["phase"] = "ORDER"
    enemy_action = _enemy_action(state, rng)
    order = _order_actions(state, action, enemy_action, rng)
    _log(
        state,
        "ORDER",
        "Las acciones quedan ordenadas.",
        order=[{"side": row["side"], "priority": row["priority"], "speed": row["speed"]} for row in order],
    )

    for row in order:
        if state.get("status") != ACTIVE_STATUS:
            break
        previous_count = len(_list(state.get("world_requests")))
        _execute_action(state, row, rng)
        if row.get("side") == "PLAYER":
            _resolve_new_world_requests(actor, state, previous_count)
        if state.get("status") != ACTIVE_STATUS:
            break
        state["phase"] = "REACTION"
        _log(state, "REACTION_WINDOW", "Se comprueba reacción y efectos inmediatos.", actor=row["side"])
        _end_check(state)

    _apply_round_end(state)
    if state.get("status") == ACTIVE_STATUS:
        state["turn"] = _int(state.get("turn"), 1) + 1
        state["phase"] = "COMMAND"
    state["pending_player_action"] = None
    state["updated_at"] = int(time())
    return {
        "accepted": True,
        "status": "WORLD_ROUND_RESOLVED",
        "battle": state,
        "enemy_action": enemy_action,
        "build": WORLD_ROUND_BUILD,
        "engine_build": BATTLE_BUILD,
    }
