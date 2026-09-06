"""Persistent actor/runtime bridge for POKEROL Pokémon battles."""

from copy import deepcopy

from services.pokemon_battle_engine import (
    ACTIVE_STATUS,
    BATTLE_BUILD,
    COMPLETE_STATUS,
    create_battle,
    public_battle_state,
    resolve_player_action,
)


RUNTIME_BUILD = "0.1.0-pokemon-battle-runtime"


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


def _site_from_actor(actor):
    room = getattr(actor, "location", None)
    if not room:
        return {}
    biome = _dict(getattr(room.db, "biome_profile", {}))
    return {
        "room_id": _text(getattr(room.db, "room_id", "")),
        "name": _text(getattr(room, "key", "")),
        "terrain": _list(biome.get("terrain")),
        "weather": _text(_dict(getattr(room.db, "world_state", {})).get("weather")) or "mild",
        "water_bodies": _list(getattr(room.db, "water_bodies", [])),
        "world_state": _dict(getattr(room.db, "world_state", {})),
        "scene_image": _dict(getattr(room.db, "scene_image", {})),
    }


def current_battle(actor):
    return _dict(getattr(actor.db, "pokerol_pokemon_battle", {})) if actor else {}


def emit_battle_state(actor, battle, *, event="STATE"):
    if not actor:
        return False
    packet = public_battle_state(battle)
    packet["runtime_build"] = RUNTIME_BUILD
    packet["event"] = str(event or "STATE").upper()
    actor.msg(pokerol_pokemon_battle_state=((packet,), {"build": RUNTIME_BUILD}))
    return True


def start_pokemon_battle(actor, player_pokemon, enemy_pokemon, *, battle_kind="WILD", source_event_id=""):
    if not actor:
        return {"accepted": False, "status": "NO_ACTOR", "build": RUNTIME_BUILD}
    existing = current_battle(actor)
    if existing and _text(existing.get("status")) == ACTIVE_STATUS:
        return {
            "accepted": False,
            "status": "BATTLE_ALREADY_ACTIVE",
            "battle": public_battle_state(existing),
            "build": RUNTIME_BUILD,
        }
    battle = create_battle(
        player_pokemon,
        enemy_pokemon,
        site=_site_from_actor(actor),
        battle_kind=battle_kind,
        source_event_id=source_event_id,
    )
    actor.db.pokerol_pokemon_battle = battle
    emit_battle_state(actor, battle, event="START")
    return {"accepted": True, "status": "BATTLE_STARTED", "battle": public_battle_state(battle), "build": RUNTIME_BUILD}


def submit_player_battle_action(actor, action):
    if not actor:
        return {"accepted": False, "status": "NO_ACTOR", "build": RUNTIME_BUILD}
    battle = current_battle(actor)
    if not battle:
        return {"accepted": False, "status": "NO_BATTLE", "build": RUNTIME_BUILD}
    result = resolve_player_action(battle, action)
    if not result.get("accepted"):
        actor.msg(pokerol_pokemon_battle_error=(({
            "status": result.get("status"),
            "battle_id": battle.get("battle_id"),
            "build": RUNTIME_BUILD,
        },), {}))
        return {**result, "build": RUNTIME_BUILD}
    next_battle = _dict(result.get("battle"))
    actor.db.pokerol_pokemon_battle = next_battle
    emit_battle_state(actor, next_battle, event="END" if next_battle.get("status") == COMPLETE_STATUS else "ROUND")
    if next_battle.get("status") == COMPLETE_STATUS:
        actor.db.last_pokemon_battle = public_battle_state(next_battle)
        actor.msg(pokerol_pokemon_battle_ended=(({
            "battle_id": next_battle.get("battle_id"),
            "outcome": next_battle.get("outcome"),
            "source_event_id": next_battle.get("source_event_id"),
            "world_requests": _clone(next_battle.get("world_requests") or []),
            "build": RUNTIME_BUILD,
            "engine_build": BATTLE_BUILD,
        },), {}))
    return {"accepted": True, "status": result.get("status"), "battle": public_battle_state(next_battle), "build": RUNTIME_BUILD}


def abandon_battle(actor):
    battle = current_battle(actor)
    if not battle:
        return {"accepted": False, "status": "NO_BATTLE", "build": RUNTIME_BUILD}
    if battle.get("status") == ACTIVE_STATUS:
        battle["status"] = COMPLETE_STATUS
        battle["phase"] = "COMPLETE"
        battle["outcome"] = "ABANDONED"
        battle.setdefault("log", []).append({
            "turn": battle.get("turn", 1),
            "phase": "COMPLETE",
            "kind": "BATTLE_END",
            "text": "La batalla fue abandonada por una orden de depuración.",
        })
    actor.db.pokerol_pokemon_battle = battle
    actor.db.last_pokemon_battle = public_battle_state(battle)
    emit_battle_state(actor, battle, event="END")
    return {"accepted": True, "status": "BATTLE_ABANDONED", "battle": public_battle_state(battle), "build": RUNTIME_BUILD}
