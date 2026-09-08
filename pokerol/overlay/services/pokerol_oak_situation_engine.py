"""Director-level situation logic for Oak's first rival challenge.

The event is intentionally not a yes/no branch. The player may fight in the
current lab, ask to go outside, postpone or refuse. Free-chat routing can call
this service; buttons are merely shortcuts to the same authority.
"""

from copy import deepcopy

from services.pokerol_event_progress import mark_event_active, snooze_event
from services.pokerol_event_editor_service import OAK_TUTORIAL_EVENT_ID
from services.pokemon_battle_runtime import start_pokemon_battle
from services.pokemon_party_engine import battle_profile_for_slot, set_active_slot, set_party_slot_profile
from services.pokerol_tutorial_engine import (
    LAB_ROOM_ID,
    RIVAL_NPC_ID,
    SPECIES_NAMES,
    TUTORIAL_BATTLE_SOURCE,
    _emit_dialogue,
    _event_line,
    _fallback_starter,
    _find_npc,
    _starter_level,
    _starter_profile,
    tutorial_state,
)


OAK_SITUATION_BUILD = "0.2.0-battle-attacks-ready"


def _text(value):
    return str(value or "").strip()


def _dict(value):
    try:
        return dict(value or {})
    except Exception:
        return {}


def _room_id(room):
    return _text(getattr(getattr(room, "db", None), "room_id", "")) if room else ""


def _save_state(actor, state):
    state = deepcopy(dict(state or {}))
    actor.db.pokerol_tutorial = state
    return state


def _outside_exit(room):
    exits = [ex for ex in list(getattr(room, "exits", []) or []) if getattr(ex, "destination", None) is not None]
    if not exits:
        return None
    def score(ex):
        label = _text(getattr(ex, "key", "")).lower()
        destination = getattr(ex, "destination", None)
        dest_id = _room_id(destination)
        value = 0
        if dest_id and dest_id != LAB_ROOM_ID:
            value += 20
        if any(word in label for word in ("afuera", "salida", "exterior", "outside", "plaza", "pueblo")):
            value += 20
        return value
    exits.sort(key=score, reverse=True)
    return exits[0]


def _rival_label():
    rival = _find_npc(RIVAL_NPC_ID)
    return _text(getattr(rival, "key", "")) or "Rival"


def _moves(profile):
    if not isinstance(profile, dict):
        return []
    rows = profile.get("moves") or profile.get("resolved_moves") or []
    return [row for row in rows if isinstance(row, dict) and _text(row.get("move_id"))]


def _ensure_player_attacks(actor, state, slot, player):
    if _moves(player):
        return player
    starter_id = _text(state.get("starter_id"))
    fallback = _fallback_starter(starter_id, level=_starter_level(actor)) if starter_id else None
    if not fallback or not _moves(fallback):
        return player
    player = deepcopy(player)
    player["moves"] = deepcopy(fallback.get("moves") or [])
    player["resolved_moves"] = deepcopy(player["moves"])
    set_party_slot_profile(actor, slot, player)
    return player


def _ensure_enemy_attacks(actor, rival_id, enemy):
    if _moves(enemy):
        return enemy
    fallback = _fallback_starter(rival_id, level=_starter_level(actor))
    if not fallback or not _moves(fallback):
        return enemy
    enemy = deepcopy(enemy)
    enemy["moves"] = deepcopy(fallback.get("moves") or [])
    enemy["resolved_moves"] = deepcopy(enemy["moves"])
    return enemy


def _start_battle_in_current_room(actor, state):
    slot = state.get("starter_slot")
    if slot is None:
        return {"accepted": False, "status": "STARTER_SLOT_MISSING", "build": OAK_SITUATION_BUILD}
    active = set_active_slot(actor, slot, require_able=True)
    if not active.get("accepted"):
        return {"accepted": False, "status": active.get("status"), "build": OAK_SITUATION_BUILD}
    player = battle_profile_for_slot(actor, slot)
    rival_id = _text(state.get("rival_starter_id"))
    enemy = _starter_profile(rival_id, level=_starter_level(actor))
    if not player or not enemy:
        return {"accepted": False, "status": "BATTLE_PROFILE_MISSING", "build": OAK_SITUATION_BUILD}
    player = _ensure_player_attacks(actor, state, slot, player)
    enemy = _ensure_enemy_attacks(actor, rival_id, enemy)
    if not _moves(player) or not _moves(enemy):
        return {"accepted": False, "status": "BATTLE_MOVES_MISSING", "build": OAK_SITUATION_BUILD}
    enemy = deepcopy(enemy)
    enemy["wild"] = False
    enemy["owner_id"] = RIVAL_NPC_ID
    rival_name = SPECIES_NAMES.get(rival_id, "Pokémon")
    _emit_dialogue(
        actor,
        _rival_label(),
        _event_line(actor, "rival_battle_start", "¡Vamos, {rival}! ¡Muéstrale lo que podemos hacer!", rival=rival_name),
    )
    result = start_pokemon_battle(
        actor,
        player,
        enemy,
        battle_kind="TRAINER",
        source_event_id=TUTORIAL_BATTLE_SOURCE,
    )
    if result.get("accepted"):
        state["stage"] = "BATTLE"
        state["battle_id"] = _text(_dict(result.get("battle")).get("battle_id"))
        state["battle_room_id"] = _room_id(getattr(actor, "location", None))
        state["challenge_status"] = "BATTLE_STARTED"
        _save_state(actor, state)
        mark_event_active(
            actor,
            OAK_TUTORIAL_EVENT_ID,
            stage="BATTLE",
            facts={
                "battle_room_id": state.get("battle_room_id"),
                "challenge_choice": state.get("challenge_choice"),
            },
        )
    return {**result, "tutorial_state": state, "build": OAK_SITUATION_BUILD}


def negotiate_rival_challenge(actor, choice):
    state = dict(tutorial_state(actor) or {})
    if str(state.get("stage") or "").upper() != "RIVAL_CHALLENGE":
        return {"accepted": False, "status": "RIVAL_CHALLENGE_NOT_READY", "state": state, "build": OAK_SITUATION_BUILD}
    wanted = _text(choice).upper()
    if wanted not in {"HERE", "OUTSIDE", "POSTPONE", "DECLINE"}:
        return {"accepted": False, "status": "BAD_CHALLENGE_CHOICE", "state": state, "build": OAK_SITUATION_BUILD}

    state["challenge_choice"] = wanted
    state["challenge_status"] = wanted

    if wanted == "POSTPONE":
        _save_state(actor, state)
        snooze_event(actor, OAK_TUTORIAL_EVENT_ID, stage="RIVAL_CHALLENGE", facts={"challenge_choice": wanted})
        _emit_dialogue(actor, _rival_label(), _event_line(actor, "rival_postpone", "¿Ahora no? Está bien. Luego lo resolvemos."))
        return {"accepted": True, "status": "CHALLENGE_POSTPONED", "state": state, "build": OAK_SITUATION_BUILD}

    if wanted == "DECLINE":
        _save_state(actor, state)
        snooze_event(actor, OAK_TUTORIAL_EVENT_ID, stage="RIVAL_CHALLENGE", facts={"challenge_choice": wanted})
        _emit_dialogue(actor, _rival_label(), _event_line(actor, "rival_decline", "¿En serio? Tch. Haz lo que quieras."))
        return {"accepted": True, "status": "CHALLENGE_DECLINED", "state": state, "build": OAK_SITUATION_BUILD}

    room = getattr(actor, "location", None)
    if wanted == "HERE":
        state["battle_room_id"] = _room_id(room)
        _save_state(actor, state)
        if state["battle_room_id"] == LAB_ROOM_ID:
            _emit_dialogue(actor, "Profesor Oak", _event_line(actor, "oak_lab_warning", "Si van a pelear aquí, mantengan el control."))
        return _start_battle_in_current_room(actor, state)

    if _room_id(room) == LAB_ROOM_ID:
        exit_obj = _outside_exit(room)
        if not exit_obj or not getattr(exit_obj, "destination", None):
            return {"accepted": False, "status": "NO_OUTSIDE_EXIT", "state": state, "build": OAK_SITUATION_BUILD}
        destination = exit_obj.destination
        rival = _find_npc(RIVAL_NPC_ID)
        _emit_dialogue(actor, _rival_label(), _event_line(actor, "rival_outside", "Bien. Afuera tendremos espacio. ¡Vamos!"))
        if rival:
            rival.move_to(destination)
        actor.move_to(destination)
        state["challenge_status"] = "READY_OUTSIDE"
        state["battle_room_id"] = _room_id(destination)
        state["relocated_via_exit"] = _text(getattr(exit_obj, "key", ""))
        _save_state(actor, state)
    else:
        state["challenge_status"] = "READY_OUTSIDE"
        state["battle_room_id"] = _room_id(room)
        _save_state(actor, state)

    return _start_battle_in_current_room(actor, state)