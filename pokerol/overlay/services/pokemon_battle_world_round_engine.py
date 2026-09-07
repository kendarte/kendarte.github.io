"""Resolve environment-targeted battle rounds as authoritative WEGO turns.

Both sides declare before resolution. World effects then execute at the real
priority/speed/position order and mutate the Room through the World Engine.
"""

import random
from copy import deepcopy
from time import time

from services.pokemon_battle_engine import (
    ACTIVE_STATUS,
    BATTLE_BUILD,
    _apply_round_end,
    _end_check,
    _log,
    _order_actions,
    move_by_id,
    validate_player_action,
)
from services.pokemon_battle_environment_engine import execute_battle_environment_request
from services.pokemon_battle_move_position_bridge import apply_world_move_position_followthrough
from services.pokemon_battle_physics_impact_engine import apply_world_physics_to_battle
from services.pokemon_battle_tactical_action_engine import enemy_action_position_aware, execute_row_position_aware
from services.pokerol_battle_scene_reaction_engine import apply_battle_scene_reactions


WORLD_ROUND_BUILD = "0.4.0-wego-reactive-world-round"


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
        position_result = apply_world_move_position_followthrough(state, "PLAYER", move, world_result, request=request)
        scene_reaction = apply_battle_scene_reactions(actor, state, move, world_result, request=request)
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
            "position_followthrough": _clone(position_result),
            "scene_reaction": _clone(scene_reaction),
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
            if position_result.get("applied"):
                _log(
                    state,
                    "POSITION_CHANGED",
                    position_result.get("text") or "El movimiento cambia la posición.",
                    actor=player.get("entity_id"),
                    move_id=move.get("move_id"),
                    position=position_result.get("position"),
                )
            if scene_reaction.get("reacted"):
                _log(
                    state,
                    "SCENE_REACTION",
                    "La escena reacciona a las consecuencias físicas del combate.",
                    reaction_status=scene_reaction.get("status"),
                    npc_id=scene_reaction.get("npc_id"),
                    target_name=scene_reaction.get("target_name"),
                )
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
        if state.get("status") != ACTIVE_STATUS:
            break
    if changed:
        state["world_requests"] = requests[-80:]
        state["last_world_resolution"] = _clone(_dict(requests[-1].get("resolution"))) if requests else None
    return changed


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
        "Ambos bandos declaran su intención antes de resolver el turno y sus efectos sobre el escenario.",
        player_action=_clone(player_action),
        enemy_action=_clone(enemy_action),
        order=_clone(declaration["resolution_order"]),
    )
    return enemy_action, order


def resolve_environment_player_action(actor, battle, action, *, rng=None):
    """Resolve one WEGO environment order with physics at its actual initiative."""
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
        return {"accepted": False, "status": "NOT_ENVIRONMENT_MOVE_ORDER", "battle": state, "build": WORLD_ROUND_BUILD}

    state["pending_player_action"] = _clone(action)
    state["phase"] = "ORDER"
    enemy_action, order = _declare_wego_round(state, action, rng)

    for row in order:
        if state.get("status") != ACTIVE_STATUS:
            break
        previous_count = len(_list(state.get("world_requests")))
        execute_row_position_aware(state, row, rng)
        if row.get("side") == "PLAYER":
            _resolve_new_world_requests(actor, state, previous_count)
        if state.get("status") != ACTIVE_STATUS:
            break
        state["phase"] = "REACTION"
        _log(
            state,
            "REACTION_WINDOW",
            "La intención revelada cruza alcance, cobertura, defensas y efectos inmediatos del escenario.",
            actor=row["side"],
        )
        _end_check(state)

    if state.get("status") == ACTIVE_STATUS:
        _apply_round_end(state)
    if state.get("status") == ACTIVE_STATUS:
        state["turn"] = _int(state.get("turn"), 1) + 1
        state["phase"] = "COMMAND"
    state["pending_player_action"] = None
    state.pop("round_declaration", None)
    state["updated_at"] = int(time())
    return {
        "accepted": True,
        "status": "WORLD_WEGO_ROUND_RESOLVED",
        "battle": state,
        "enemy_action": enemy_action,
        "round_declaration": _clone(state.get("last_round_declaration")),
        "build": WORLD_ROUND_BUILD,
        "engine_build": BATTLE_BUILD,
    }