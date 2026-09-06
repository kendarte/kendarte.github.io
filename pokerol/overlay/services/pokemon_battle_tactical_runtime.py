"""Persistent runtime facade for position-aware POKEROL battle actions."""

from copy import deepcopy

from services.pokemon_battle_engine import ACTIVE_STATUS, COMPLETE_STATUS, BATTLE_BUILD
from services.pokemon_battle_position_engine import position_label, position_targets
from services.pokemon_battle_runtime import (
    RUNTIME_BUILD,
    _basic_action_gate,
    _promote_forced_switch_if_possible,
    _public_state,
    _resolve_source_travel_event,
    current_battle,
    emit_battle_state,
    submit_player_battle_action,
)
from services.pokemon_battle_tactical_round_engine import resolve_tactical_player_action
from services.pokemon_party_engine import update_owned_from_battle


TACTICAL_RUNTIME_BUILD = "0.1.0-persistent-position-runtime"


def _dict(value):
    try:
        return dict(value or {})
    except Exception:
        return {}


def _clone(value):
    return deepcopy(value)


def _text(value):
    return str(value or "").strip()


def position_options_packet(actor):
    battle = current_battle(actor)
    if not battle:
        return {
            "accepted": False,
            "status": "NO_BATTLE",
            "targets": [],
            "build": TACTICAL_RUNTIME_BUILD,
        }
    if _text(battle.get("status")).upper() != ACTIVE_STATUS:
        return {
            "accepted": False,
            "status": "BATTLE_NOT_ACTIVE",
            "targets": [],
            "build": TACTICAL_RUNTIME_BUILD,
        }
    player = _dict(battle.get("player"))
    return {
        "accepted": True,
        "status": "POSITION_OPTIONS",
        "battle_id": battle.get("battle_id"),
        "position": _clone(player.get("battle_position") or {}),
        "position_label": position_label(player),
        "targets": position_targets(actor, battle, side="PLAYER"),
        "build": TACTICAL_RUNTIME_BUILD,
    }


def emit_position_options(actor):
    packet = position_options_packet(actor)
    if actor:
        actor.msg(pokerol_pokemon_position_options=((packet,), {"build": TACTICAL_RUNTIME_BUILD}))
    return packet


def _finalize_tactical_result(actor, result):
    if not result.get("accepted"):
        battle = current_battle(actor)
        actor.msg(pokerol_pokemon_battle_error=(({
            "status": result.get("status"),
            "battle_id": battle.get("battle_id") if battle else None,
            "build": TACTICAL_RUNTIME_BUILD,
        },), {}))
        if battle:
            emit_battle_state(actor, battle, event="STATE")
        return {**result, "build": TACTICAL_RUNTIME_BUILD}

    next_battle = _dict(result.get("battle"))
    update_owned_from_battle(actor, _dict(next_battle.get("player")))
    _promote_forced_switch_if_possible(actor, next_battle)

    if _text(next_battle.get("status")).upper() == COMPLETE_STATUS:
        next_battle["travel_event_resolution"] = _clone(_resolve_source_travel_event(actor, next_battle))

    actor.db.pokerol_pokemon_battle = next_battle
    is_complete = _text(next_battle.get("status")).upper() == COMPLETE_STATUS
    emit_battle_state(actor, next_battle, event="END" if is_complete else "ROUND")

    if is_complete:
        actor.db.last_pokemon_battle = _public_state(actor, next_battle)
        actor.msg(pokerol_pokemon_battle_ended=(({
            "battle_id": next_battle.get("battle_id"),
            "outcome": next_battle.get("outcome"),
            "source_event_id": next_battle.get("source_event_id"),
            "world_requests": _clone(next_battle.get("world_requests") or []),
            "collection_result": None,
            "travel_event_resolution": _clone(next_battle.get("travel_event_resolution")),
            "build": TACTICAL_RUNTIME_BUILD,
            "runtime_build": RUNTIME_BUILD,
            "engine_build": BATTLE_BUILD,
        },), {}))

    return {
        "accepted": True,
        "status": result.get("status"),
        "battle": _public_state(actor, next_battle),
        "build": TACTICAL_RUNTIME_BUILD,
    }


def submit_tactical_battle_action(actor, action):
    """Route tactical actions while preserving the existing item/capture/world runtime."""
    if not actor:
        return {"accepted": False, "status": "NO_ACTOR", "build": TACTICAL_RUNTIME_BUILD}
    action = _dict(action)
    kind = _text(action.get("type")).upper()
    position_action = _text(action.get("position_action")).upper()

    # Existing runtime remains authority for capture, items, switches, run and
    # move-to-world physics. Direct moves and explicit position changes use the
    # spatial resolver.
    tactical = kind == "MOVE" or (kind == "FREE_ORDER" and bool(position_action))
    if not tactical:
        return submit_player_battle_action(actor, action)

    battle = current_battle(actor)
    if not battle:
        return {"accepted": False, "status": "NO_BATTLE", "build": TACTICAL_RUNTIME_BUILD}
    gate = _basic_action_gate(battle, "POSITION" if position_action else kind)
    if gate:
        return _finalize_tactical_result(actor, {
            "accepted": False,
            "status": gate,
            "battle": battle,
        })

    result = resolve_tactical_player_action(actor, battle, action)
    return _finalize_tactical_result(actor, result)
