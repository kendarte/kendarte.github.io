"""Persistent actor/runtime bridge for POKEROL Pokémon battles."""

from copy import deepcopy

from services.pokemon_bag_engine import (
    apply_battle_item,
    bag_state,
    capture_ball_profile,
    consume_item,
    item_count,
    item_profile,
)
from services.pokemon_battle_engine import (
    ACTIVE_STATUS,
    BATTLE_BUILD,
    COMPLETE_STATUS,
    create_battle,
    move_by_id,
    normalize_pokemon,
    public_battle_state,
    resolve_player_action,
)
from services.pokemon_battle_environment_engine import (
    environment_targets,
    execute_battle_environment_request,
)
from services.pokemon_party_engine import (
    able_party_slots,
    active_pokemon,
    active_slot,
    add_pokemon,
    battle_profile_for_slot,
    party_state,
    set_active_slot,
    set_party_slot_profile,
    update_owned_from_battle,
)


RUNTIME_BUILD = "0.5.0-anime-environment-bridge"


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
    packet["environment_targets"] = environment_targets(actor)
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
            "species_id": enemy.get("species_id"), "species_name": enemy.get("species_name") or enemy.get("name"),
            "level": enemy.get("level"), "types": _clone(enemy.get("types") or []),
            "moves": _clone(enemy.get("moves") or []), "resolved_moves": _clone(enemy.get("moves") or []),
            "sprite": _clone(enemy.get("sprite") or {}),
        }
    source.pop("instance_id", None)
    source.pop("entity_id", None)
    source["level"] = enemy.get("level", source.get("level"))
    source["hp_current"] = enemy.get("hp_current")
    source["hp_max"] = enemy.get("hp_max")
    source["status"] = enemy.get("status")
    source["status_turns"] = enemy.get("status_turns", 0)
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

    forced = bool(battle.get("forced_switch"))
    update_owned_from_battle(actor, _dict(battle.get("player")))
    switched = set_active_slot(actor, target_slot, require_able=True)
    if not switched.get("accepted"):
        return {"accepted": False, "status": switched.get("status"), "build": RUNTIME_BUILD}

    next_state = _clone(battle)
    incoming = normalize_pokemon(profile, side="PLAYER")
    next_state["player"] = incoming
    next_state["_source_player_profile"] = _clone(profile)
    next_state.pop("forced_switch", None)
    next_state.pop("available_switch_slots", None)
    next_state["status"] = ACTIVE_STATUS
    next_state["phase"] = "COMMAND"
    next_state["outcome"] = ""
    next_state.setdefault("log", []).append({
        "turn": next_state.get("turn", 1), "phase": "SWITCH", "kind": "SWITCH",
        "text": f"¡Adelante, {incoming.get('name')}!", "actor": incoming.get("entity_id"), "party_slot": target_slot,
    })
    if forced:
        return {"accepted": True, "status": "FORCED_SWITCH_RESOLVED", "battle": next_state, "enemy_action": None, "build": BATTLE_BUILD}
    return resolve_player_action(next_state, {"type": "FREE_ORDER", "switch_slot": target_slot})


def _support_item_action(actor, battle, action):
    item_id = _text(_dict(action).get("item_id")).upper()
    if not item_id:
        return {"accepted": False, "status": "ITEM_ID_REQUIRED", "build": RUNTIME_BUILD}
    profile = item_profile(item_id)
    if not profile:
        return {"accepted": False, "status": "UNKNOWN_ITEM", "item_id": item_id, "build": RUNTIME_BUILD}
    if profile.get("kind") in {"CAPTURE", "CAPTURE_RESERVED"}:
        return {"accepted": False, "status": "USE_CAPTURE_ACTION_FOR_BALL", "item_id": item_id, "build": RUNTIME_BUILD}
    if item_count(actor, item_id) <= 0:
        return {"accepted": False, "status": "ITEM_NOT_AVAILABLE", "item_id": item_id, "build": RUNTIME_BUILD}

    current_slot = active_slot(actor)
    target_slot = _int(_dict(action).get("slot"), current_slot)
    if target_slot < 0:
        return {"accepted": False, "status": "NO_ITEM_TARGET", "item_id": item_id, "build": RUNTIME_BUILD}
    active_target = target_slot == current_slot
    target = _clone(_dict(battle.get("player"))) if active_target else _dict(battle_profile_for_slot(actor, target_slot))
    if not target:
        return {"accepted": False, "status": "INVALID_PARTY_SLOT", "item_id": item_id, "build": RUNTIME_BUILD}

    effect = apply_battle_item(item_id, target, move_id=_text(_dict(action).get("move_id")))
    if not effect.get("accepted"):
        return {**effect, "build": RUNTIME_BUILD}
    consumed = consume_item(actor, item_id, 1)
    if not consumed.get("accepted"):
        return {"accepted": False, "status": consumed.get("status"), "item_id": item_id, "build": RUNTIME_BUILD}

    mutated = _dict(effect.get("pokemon"))
    next_state = _clone(battle)
    if active_target:
        next_state["player"] = mutated
    else:
        stored = set_party_slot_profile(actor, target_slot, mutated)
        if not stored.get("accepted"):
            return {"accepted": False, "status": stored.get("status"), "item_id": item_id, "build": RUNTIME_BUILD}

    next_state.setdefault("log", []).append({
        "turn": next_state.get("turn", 1), "phase": "ACTION", "kind": "ITEM",
        "text": effect.get("text") or f"Usas {item_id}.", "item_id": item_id,
        "party_slot": target_slot, "move_id": _text(_dict(action).get("move_id")) or None,
    })
    result = resolve_player_action(next_state, {"type": "FREE_ORDER", "item_id": item_id, "party_slot": target_slot})
    if result.get("accepted"):
        result["item_result"] = _clone(effect)
        result["item_consumed"] = _clone(consumed)
    return result


def _resolve_pending_world_requests(actor, battle):
    requests = _list(battle.get("world_requests"))
    if not requests:
        return []
    player = _dict(battle.get("player"))
    resolved_rows = []
    for raw in requests:
        request = _dict(raw)
        if _text(request.get("status")) != "PENDING_WORLD_RESOLUTION":
            resolved_rows.append(request)
            continue
        if _text(request.get("actor_entity_id")) != _text(player.get("entity_id")):
            request["status"] = "WORLD_ACTOR_NOT_SUPPORTED"
            request["resolution"] = {"executed": False, "status": "WORLD_ACTOR_NOT_SUPPORTED"}
            resolved_rows.append(request)
            continue
        move = move_by_id(player, request.get("move_id"))
        if not move:
            request["status"] = "WORLD_MOVE_MISSING"
            request["resolution"] = {"executed": False, "status": "WORLD_MOVE_MISSING"}
            resolved_rows.append(request)
            continue

        result = execute_battle_environment_request(actor, player, move, request)
        executed = bool(result.get("executed"))
        request["status"] = "WORLD_EXECUTED" if executed else "WORLD_REJECTED"
        request["resolution"] = {
            "executed": executed,
            "status": result.get("status"),
            "target_dbref": result.get("target_dbref"),
            "persisted_target_state": _clone(_dict(result.get("persisted_target_state"))),
            "events": _clone(_list(result.get("events"))),
            "area_impacts": _clone(_list(result.get("area_impacts"))),
            "persisted_area_impacts": _clone(_list(result.get("persisted_area_impacts"))),
        }
        target_spec = _dict(request.get("world_target"))
        target_name = _text(target_spec.get("name") or target_spec.get("object_id")) or "el entorno"
        if executed:
            battle.setdefault("log", []).append({
                "turn": request.get("turn"), "phase": "RESOLUTION", "kind": "WORLD_EFFECT",
                "text": f"El efecto físico alcanza {target_name}.", "request_id": request.get("request_id"),
                "world_status": result.get("status"),
            })
        else:
            battle.setdefault("log", []).append({
                "turn": request.get("turn"), "phase": "RESOLUTION", "kind": "WORLD_EFFECT_REJECTED",
                "text": f"La interacción con {target_name} no produce un efecto físico válido.",
                "request_id": request.get("request_id"), "world_status": result.get("status"),
            })
        resolved_rows.append(request)
    battle["world_requests"] = resolved_rows[-80:]
    battle["last_world_resolution"] = _clone(resolved_rows[-1].get("resolution")) if resolved_rows else None
    return resolved_rows


def _basic_action_gate(battle, requested_kind=""):
    if _text(battle.get("status")).upper() != ACTIVE_STATUS:
        return "BATTLE_NOT_ACTIVE"
    if _text(battle.get("phase")).upper() != "COMMAND":
        return "NOT_COMMAND_PHASE"
    if bool(battle.get("forced_switch")) and _text(requested_kind).upper() != "SWITCH":
        return "FORCED_SWITCH_REQUIRED"
    return ""


def _promote_forced_switch_if_possible(actor, battle):
    if _text(battle.get("status")).upper() != COMPLETE_STATUS or _text(battle.get("outcome")).upper() != "PLAYER_LOSS":
        return False
    player = _dict(battle.get("player"))
    if _int(player.get("hp_current"), 0) > 0:
        return False
    slots = able_party_slots(actor, exclude_slot=active_slot(actor))
    if not slots:
        return False
    battle["status"] = ACTIVE_STATUS
    battle["phase"] = "COMMAND"
    battle["outcome"] = ""
    battle["forced_switch"] = True
    battle["available_switch_slots"] = slots
    battle["turn"] = _int(battle.get("turn"), 1) + 1
    battle.setdefault("log", []).append({
        "turn": battle.get("turn"), "phase": "SWITCH", "kind": "FORCED_SWITCH",
        "text": f"{player.get('name')} está fuera de combate. Elige otro Pokémon.",
    })
    return True


def _resolve_source_travel_event(actor, battle):
    source_event_id = _text(battle.get("source_event_id"))
    if not source_event_id:
        return None
    pending = _dict(getattr(actor.db, "pending_travel_event", {}))
    if _text(pending.get("travel_event_id")) != source_event_id:
        return None
    outcome = _text(battle.get("outcome")).upper()
    resolution = {
        "PLAYER_WIN": "WILD_DEFEATED", "PLAYER_LOSS": "PLAYER_DEFEATED", "CAPTURED": "CAPTURED",
        "ESCAPED": "ESCAPED", "DRAW": "DRAW", "ABANDONED": "ABANDONED",
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
    requested = _clone(_dict(action))
    kind = _text(requested.get("type")).upper()
    gate = _basic_action_gate(battle, kind)
    if gate:
        actor.msg(pokerol_pokemon_battle_error=(({"status": gate, "battle_id": battle.get("battle_id"), "build": RUNTIME_BUILD},), {}))
        return {"accepted": False, "status": gate, "build": RUNTIME_BUILD}

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
    elif kind == "ITEM":
        result = _support_item_action(actor, battle, requested)
    else:
        result = resolve_player_action(battle, requested)

    if not result.get("accepted"):
        actor.msg(pokerol_pokemon_battle_error=(({"status": result.get("status"), "battle_id": battle.get("battle_id"), "build": RUNTIME_BUILD},), {}))
        emit_battle_state(actor, battle, event="STATE")
        return {**result, "build": RUNTIME_BUILD}

    next_battle = _dict(result.get("battle"))
    _resolve_pending_world_requests(actor, next_battle)
    update_owned_from_battle(actor, _dict(next_battle.get("player")))
    _promote_forced_switch_if_possible(actor, next_battle)

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
