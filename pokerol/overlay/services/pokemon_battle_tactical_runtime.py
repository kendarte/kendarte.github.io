"""Persistent runtime facade for position-aware POKEROL battle actions."""

from copy import deepcopy

from services.pokemon_battle_engine import ACTIVE_STATUS, COMPLETE_STATUS, BATTLE_BUILD
from services.pokemon_battle_position_engine import position_label, position_targets
from services.pokemon_battle_reaction_engine import reaction_state
from services.pokemon_battle_reaction_window_engine import apply_choice, public_window
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
from services.pokemon_battle_shot_director import emit_battle_shots
from services.pokemon_battle_tactical_round_engine import (
    resolve_tactical_player_action,
    resume_tactical_reaction,
)
from services.pokemon_party_engine import update_owned_from_battle


TACTICAL_RUNTIME_BUILD = "0.5.0-contextual-reaction-window-runtime"


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


def _clone(value):
    return deepcopy(value)


def _text(value):
    return str(value or "").strip()


def position_options_packet(actor):
    battle = current_battle(actor)
    if not battle:
        return {"accepted": False, "status": "NO_BATTLE", "targets": [], "build": TACTICAL_RUNTIME_BUILD}
    if _text(battle.get("status")).upper() != ACTIVE_STATUS:
        return {"accepted": False, "status": "BATTLE_NOT_ACTIVE", "targets": [], "build": TACTICAL_RUNTIME_BUILD}
    player = _dict(battle.get("player"))
    return {
        "accepted": True,
        "status": "POSITION_OPTIONS",
        "battle_id": battle.get("battle_id"),
        "position": _clone(player.get("battle_position") or {}),
        "position_label": position_label(player),
        "targets": position_targets(actor, battle, side="PLAYER"),
        "reaction": reaction_state(player),
        "build": TACTICAL_RUNTIME_BUILD,
    }


def emit_position_options(actor):
    packet = position_options_packet(actor)
    if actor:
        actor.msg(pokerol_pokemon_position_options=((packet,), {"build": TACTICAL_RUNTIME_BUILD}))
    return packet


def reaction_options_packet(actor):
    battle = current_battle(actor)
    window = public_window(battle)
    if not battle:
        return {"accepted": False, "status": "NO_BATTLE", "options": [], "build": TACTICAL_RUNTIME_BUILD}
    if not window:
        return {"accepted": False, "status": "NO_REACTION_WINDOW", "options": [], "build": TACTICAL_RUNTIME_BUILD}
    return {
        "accepted": True,
        "status": "REACTION_WINDOW",
        **_clone(window),
        "build": TACTICAL_RUNTIME_BUILD,
    }


def emit_reaction_options(actor):
    packet = reaction_options_packet(actor)
    if actor and packet.get("accepted"):
        actor.msg(pokerol_pokemon_reaction_window=((packet,), {"build": TACTICAL_RUNTIME_BUILD}))
    return packet


def emit_active_reaction_window(actor, battle=None):
    state = _dict(battle) or current_battle(actor)
    window = public_window(state)
    if not actor or not window:
        return False
    packet = {"accepted": True, "status": "REACTION_WINDOW", **_clone(window), "build": TACTICAL_RUNTIME_BUILD}
    actor.msg(pokerol_pokemon_reaction_window=((packet,), {"build": TACTICAL_RUNTIME_BUILD}))
    return True


def _finalize_tactical_result(actor, result, *, before=None, action=None, log_start=0):
    if not result.get("accepted"):
        battle = current_battle(actor)
        actor.msg(pokerol_pokemon_battle_error=(({
            "status": result.get("status"),
            "battle_id": battle.get("battle_id") if battle else None,
            "build": TACTICAL_RUNTIME_BUILD,
        },), {}))
        if battle:
            emit_battle_state(actor, battle, event="STATE")
            emit_active_reaction_window(actor, battle)
        return {**result, "build": TACTICAL_RUNTIME_BUILD}

    next_battle = _dict(result.get("battle"))
    update_owned_from_battle(actor, _dict(next_battle.get("player")))

    if _text(result.get("status")).upper() == "REACTION_WINDOW_OPEN":
        actor.db.pokerol_pokemon_battle = next_battle
        emit_battle_state(actor, next_battle, event="REACTION")
        emit_active_reaction_window(actor, next_battle)
        return {
            "accepted": True,
            "status": "REACTION_WINDOW_OPEN",
            "battle": _public_state(actor, next_battle),
            "reaction_window": _clone(public_window(next_battle)),
            "build": TACTICAL_RUNTIME_BUILD,
        }

    _promote_forced_switch_if_possible(actor, next_battle)
    if _text(next_battle.get("status")).upper() == COMPLETE_STATUS:
        next_battle["travel_event_resolution"] = _clone(_resolve_source_travel_event(actor, next_battle))

    actor.db.pokerol_pokemon_battle = next_battle
    is_complete = _text(next_battle.get("status")).upper() == COMPLETE_STATUS
    if before is not None and action is not None:
        emit_battle_shots(actor, before, next_battle, action, log_start=log_start, event="END" if is_complete else "ROUND")
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
            "scene_interruption": _clone(next_battle.get("scene_interruption")),
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


def submit_reaction_window_choice(actor, window_id, policy="PASS", method_move_id=""):
    if not actor:
        return {"accepted": False, "status": "NO_ACTOR", "build": TACTICAL_RUNTIME_BUILD}
    battle = current_battle(actor)
    if not battle:
        return {"accepted": False, "status": "NO_BATTLE", "build": TACTICAL_RUNTIME_BUILD}
    window = public_window(battle)
    if not window:
        return {"accepted": False, "status": "NO_REACTION_WINDOW", "build": TACTICAL_RUNTIME_BUILD}

    before = _clone(battle)
    log_start = len(_list(before.get("log")))
    action = _dict(_dict(battle.get("pending_round_resume")).get("player_action"))
    chosen = apply_choice(battle, window_id, policy, method_move_id)
    if not chosen.get("accepted"):
        return _finalize_tactical_result(actor, {"accepted": False, "status": chosen.get("status"), "battle": battle})

    result = resume_tactical_reaction(battle)
    return _finalize_tactical_result(actor, result, before=before, action=action, log_start=log_start)


def set_player_reaction(actor, policy="DODGE", method_move_id="", window_id=""):
    """Compatibility entry point: reactions are legal only inside an open window."""
    battle = current_battle(actor)
    window = public_window(battle)
    if not window:
        return {"accepted": False, "status": "NO_REACTION_WINDOW", "build": TACTICAL_RUNTIME_BUILD}
    return submit_reaction_window_choice(actor, window_id or window.get("window_id"), policy, method_move_id)


def submit_tactical_battle_action(actor, action):
    """Route tactical actions; enemy attacks pause for contextual reaction windows."""
    if not actor:
        return {"accepted": False, "status": "NO_ACTOR", "build": TACTICAL_RUNTIME_BUILD}
    action = _dict(action)
    kind = _text(action.get("type")).upper()
    position_action = _text(action.get("position_action")).upper()
    before = _clone(current_battle(actor))
    log_start = len(_list(before.get("log"))) if before else 0

    tactical = kind == "MOVE" or (kind == "FREE_ORDER" and bool(position_action))
    if not tactical:
        return submit_player_battle_action(actor, action)

    battle = current_battle(actor)
    if not battle:
        return {"accepted": False, "status": "NO_BATTLE", "build": TACTICAL_RUNTIME_BUILD}
    gate = _basic_action_gate(battle, "POSITION" if position_action else kind)
    if gate:
        return _finalize_tactical_result(actor, {"accepted": False, "status": gate, "battle": battle})

    result = resolve_tactical_player_action(actor, battle, action)
    return _finalize_tactical_result(actor, result, before=before, action=action, log_start=log_start)
