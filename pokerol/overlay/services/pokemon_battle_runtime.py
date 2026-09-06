"""Persistent actor/runtime bridge for POKEROL Pokémon battles."""

from copy import deepcopy

from services.pokemon_bag_engine import bag_state, capture_ball_profile, consume_item
from services.pokemon_battle_engine import (
    ACTIVE_STATUS,
    BATTLE_BUILD,
    COMPLETE_STATUS,
    create_battle,
    normalize_pokemon,
    public_battle_state,
    resolve_player_action,
)
from services.pokemon_party_engine import (
    active_pokemon,
    active_slot,
    add_pokemon,
    battle_profile_for_slot,
    party_state,
    set_active_slot,
    update_owned_from_battle,
)


RUNTIME_BUILD = "0.2.2-travel-event-closeout"


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


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


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


def _public_state(actor, battle):
    packet = public_battle_state(battle)
    for key in list(packet.keys()):
        if str(key).startswith("_"):
            packet.pop(key, None)
    packet["party_state"] = party_state(actor)
    packet["bag_state"] = bag_state(actor)
    return packet


def current_battle(actor):
    return _dict(getattr(actor.db, "pokerol_pokemon_battle", {})) if actor else {}


def emit_battle_state(actor, battle, *, event="STATE"):
    if not actor:
        return False
    packet = _public_state(actor, battle)
    packet["runtime_build"] = RUNTIME_BUILD
    packet["event"] = str(event or "STATE").upper()
    actor.msg(pokerol_pokemon_battle_state=((packet,), {"build": RUNTIME_BUILD}))
    return True


def start_pokemon_battle(actor, player_pokemon, enemy_pokemon, *, battle_kind="WILD", source_event_id=""):
    if not actor:
        return {"accepted": False, "status": "NO_ACTOR", "build": RUNTIME_BUILD}
    existing = current_battle(actor)
    if existing and _text(existing.get("status")) == ACTIVE_STATUS:
        return {"accepted": False, "status": "BATTLE_ALREADY_ACTIVE", "battle": _public_state(actor, existing), "build": RUNTIME_BUILD}
    chosen = _dict(player_pokemon) or _dict(active_pokemon(actor))
    if not chosen:
        return {"accepted": False, "status": "NO_ACTIVE_POKEMON", "build": RUNTIME_BUILD}
    battle = create_battle(chosen, enemy_pokemon, site=_site_from_actor(actor), battle_kind=battle_kind, source_event_id=source_event_id)
    battle["_source_enemy_profile"] = _clone(_dict(enemy_pokemon))
    battle["_source_player_profile"] = _clone(chosen)
    actor.db.pokerol_pokemon_battle = battle
    emit_battle_state(actor, battle, event="START")
    return {"accepted": True, "status": "BATTLE_STARTED", "battle": _public_state(actor, battle), "build": RUNTIME_BUILD}


def start_pokemon_battle_from_party(actor, enemy_pokemon, *, battle_kind="WILD", source_event_id=""):
    chosen = active_pokemon(actor)
    if not chosen:
        return {"accepted": False, "status": "NO_ACTIVE_POKEMON", "build": RUNTIME_BUILD}
    return start_pokemon_battle(actor, chosen, enemy_pokemon, battle_kind=battle_kind, source_event_id=source_event_id)


def _prepare_capture(actor, action):
    item_id = _text(_dict(action).get("item_id")) or "POKE_BALL"
    profile = capture_ball_profile(actor, item_id)
    if not profile.get("accepted"):
        return {"accepted": False, "status": profile.get("status"), "item_id": item_id}
    consumed = consume_item(actor, item_id, 1)
    if not consumed.get("accepted"):
        return {"accepted": False, "status": consumed.get("status"), "item_id": item_id}
    prepared = _clone(_dict(action))
    prepared["type"] = "CAPTURE"
    prepared["item_id"] = item_id
    prepared["ball_multiplier"] = profile.get("ball_multiplier", 1.0)
    return {"accepted": True, "status": "CAPTURE_PREPARED", "action": prepared, "item_id": item_id}


def _capture_into_collection(actor, battle):
    source = _clone(_dict(battle.get("_source_enemy_profile")))
    enemy = _dict(battle.get("enemy"))
    if not source:
        source = {
            "species_id": enemy.get("species_id"),
            "species_name": enemy.get("species_name") or enemy.get("name"),
            "level": enemy.get("level"),
            "types": _clone(enemy.get("types") or []),
            "moves": _clone(enemy.get("moves") or []),
            "resolved_moves": _clone(enemy.get("moves") or []),
            "sprite": _clone(enemy.get("sprite") or {}),
        }
    source.pop("instance_id", None)
    source.pop("entity_id", None)
    source["level"] = enemy.get("level", source.get("level"))
    source["hp_current"] = enemy.get("hp_current")
    source["hp_max"] = enemy.get("hp_max")
    source["status"] = enemy.get("status")
    source["moves"] = _clone(enemy.get("moves") or source.get("moves") or [])
    source["resolved_moves"] = _clone(source.get("moves") or [])
    source["sprite"] = _clone(enemy.get("sprite") or source.get("sprite") or {})
    source["wild"] = False
    return add_pokemon(actor, source, prefer_party=True)


def _switch_action(actor, battle, action):
    target_slot = _int(_dict(action).get("slot"), -1)
    current_slot = active_slot(actor)
    if target_slot == current_slot:
        return {"accepted": False, "status": "POKEMON_ALREADY_ACTIVE", "build": RUNTIME_BUILD}
    profile = battle_profile_for_slot(actor, target_slot)
    if not profile:
        return {"accepted": False, "status": "INVALID_PARTY_SLOT", "build": RUNTIME_BUILD}
    if _int(profile.get("hp_current"), 0) <= 0:
        return {"accepted": False, "status": "POKEMON_FAINTED", "build": RUNTIME_BUILD}
    update_owned_from_battle(actor, _dict(battle.get("player")))
    switched = set_active_slot(actor, target_slot, require_able=True)
    if not switched.get("accepted"):
        return {"accepted": False, "status": switched.get("status"), "build": RUNTIME_BUILD}
    next_state = _clone(battle)
    incoming = normalize_pokemon(profile, side="PLAYER")
    next_state["player"] = incoming
    next_state["_source_player_profile"] = _clone(profile)
    next_state.setdefault("log", []).append({
        "turn": next_state.get("turn", 1), "phase": "SWITCH", "kind": "SWITCH",
        "text": f"¡Adelante, {incoming.get('name')}!", "actor": incoming.get("entity_id"), "party_slot": target_slot,
    })
    return resolve_player_action(next_state, {"type": "FREE_ORDER", "switch_slot": target_slot})


def _basic_action_gate(battle):
    if _text(battle.get("status")).upper() != ACTIVE_STATUS:
        return "BATTLE_NOT_ACTIVE"
    if _text(battle.get("phase")).upper() != "COMMAND":
        return "NOT_COMMAND_PHASE"
    return ""


def _resolve_source_travel_event(actor, battle):
    source_event_id = _text(battle.get("source_event_id"))
    if not source_event_id:
        return None
    pending = _dict(getattr(actor.db, "pending_travel_event", {}))
    if _text(pending.get("travel_event_id")) != source_event_id:
        return None
    outcome = _text(battle.get("outcome")).upper()
    resolution = {
        "PLAYER_WIN": "WILD_DEFEATED",
        "PLAYER_LOSS": "PLAYER_DEFEATED",
        "CAPTURED": "CAPTURED",
        "ESCAPED": "ESCAPED",
        "DRAW": "DRAW",
        "ABANDONED": "ABANDONED",
    }.get(outcome, outcome or "BATTLE_RESOLVED")
    try:
        from services.travel_event_engine import resolve_pending_travel_event
        return resolve_pending_travel_event(actor, resolution, notes=f"battle_id={battle.get('battle_id')}")
    except Exception as exc:
        return {"status": "TRAVEL_EVENT_RESOLUTION_FAILED", "error": str(exc)}


def submit_player_battle_action(actor, action):
    if not actor:
        return {"accepted": False, "status": "NO_ACTOR", "build": RUNTIME_BUILD}
    battle = current_battle(actor)
    if not battle:
        return {"accepted": False, "status": "NO_BATTLE", "build": RUNTIME_BUILD}
    gate = _basic_action_gate(battle)
    if gate:
        actor.msg(pokerol_pokemon_battle_error=(({"status": gate, "battle_id": battle.get("battle_id"), "build": RUNTIME_BUILD},), {}))
        return {"accepted": False, "status": gate, "build": RUNTIME_BUILD}

    requested = _clone(_dict(action))
    kind = _text(requested.get("type")).upper()
    capture_item_id = ""

    if kind == "CAPTURE":
        if _text(battle.get("battle_kind")).upper() != "WILD" or not bool(_dict(battle.get("enemy")).get("wild")):
            return {"accepted": False, "status": "CAPTURE_NOT_ALLOWED", "build": RUNTIME_BUILD}
        prepared = _prepare_capture(actor, requested)
        if not prepared.get("accepted"):
            actor.msg(pokerol_pokemon_battle_error=(({"status": prepared.get("status"), "battle_id": battle.get("battle_id"), "build": RUNTIME_BUILD},), {}))
            emit_battle_state(actor, battle, event="STATE")
            return {"accepted": False, "status": prepared.get("status"), "build": RUNTIME_BUILD}
        requested = _dict(prepared.get("action"))
        capture_item_id = _text(prepared.get("item_id"))
        result = resolve_player_action(battle, requested)
    elif kind == "SWITCH":
        result = _switch_action(actor, battle, requested)
    else:
        result = resolve_player_action(battle, requested)

    if not result.get("accepted"):
        actor.msg(pokerol_pokemon_battle_error=(({"status": result.get("status"), "battle_id": battle.get("battle_id"), "build": RUNTIME_BUILD},), {}))
        return {**result, "build": RUNTIME_BUILD}

    next_battle = _dict(result.get("battle"))
    update_owned_from_battle(actor, _dict(next_battle.get("player")))
    collection_result = None
    if next_battle.get("status") == COMPLETE_STATUS and _text(next_battle.get("outcome")) == "CAPTURED":
        collection_result = _capture_into_collection(actor, next_battle)
        next_battle["capture_collection_result"] = _clone(collection_result)
        next_battle["capture_item_id"] = capture_item_id

    if next_battle.get("status") == COMPLETE_STATUS:
        next_battle["travel_event_resolution"] = _clone(_resolve_source_travel_event(actor, next_battle))

    actor.db.pokerol_pokemon_battle = next_battle
    emit_battle_state(actor, next_battle, event="END" if next_battle.get("status") == COMPLETE_STATUS else "ROUND")
    if next_battle.get("status") == COMPLETE_STATUS:
        actor.db.last_pokemon_battle = _public_state(actor, next_battle)
        actor.msg(pokerol_pokemon_battle_ended=(({
            "battle_id": next_battle.get("battle_id"), "outcome": next_battle.get("outcome"),
            "source_event_id": next_battle.get("source_event_id"), "world_requests": _clone(next_battle.get("world_requests") or []),
            "collection_result": _clone(collection_result), "travel_event_resolution": _clone(next_battle.get("travel_event_resolution")),
            "build": RUNTIME_BUILD, "engine_build": BATTLE_BUILD,
        },), {}))
    return {"accepted": True, "status": result.get("status"), "battle": _public_state(actor, next_battle), "build": RUNTIME_BUILD}


def abandon_battle(actor):
    battle = current_battle(actor)
    if not battle:
        return {"accepted": False, "status": "NO_BATTLE", "build": RUNTIME_BUILD}
    if battle.get("status") == ACTIVE_STATUS:
        update_owned_from_battle(actor, _dict(battle.get("player")))
        battle["status"] = COMPLETE_STATUS
        battle["phase"] = "COMPLETE"
        battle["outcome"] = "ABANDONED"
        battle.setdefault("log", []).append({"turn": battle.get("turn", 1), "phase": "COMPLETE", "kind": "BATTLE_END", "text": "La batalla fue abandonada por una orden de depuración."})
        battle["travel_event_resolution"] = _clone(_resolve_source_travel_event(actor, battle))
    actor.db.pokerol_pokemon_battle = battle
    actor.db.last_pokemon_battle = _public_state(actor, battle)
    emit_battle_state(actor, battle, event="END")
    return {"accepted": True, "status": "BATTLE_ABANDONED", "battle": _public_state(actor, battle), "build": RUNTIME_BUILD}
