"""Persistent Pallet Town tutorial: Oak, starter choice and first rival battle."""

from copy import deepcopy

from evennia import create_object
from evennia.objects.models import ObjectDB

from services.pokemon_battle_runtime import current_battle, start_pokemon_battle
from services.pokemon_party_engine import (
    add_pokemon,
    battle_profile_for_slot,
    party_state,
    set_active_slot,
    set_party_slot_profile,
)
from services.pokemon_species_registry import spawn_species_profile


TUTORIAL_BUILD = "0.1.0-oak-starter-rival"
LAB_ROOM_ID = "KANTO-PAL-002"
OAK_NPC_ID = "NPC-KANTO-PAL-OAK"
RIVAL_NPC_ID = "NPC-KANTO-PAL-RIVAL"
TUTORIAL_BATTLE_SOURCE = "TUTORIAL-RIVAL-1"
TUTORIAL_NPC_IDS = (OAK_NPC_ID, RIVAL_NPC_ID)

STARTERS = {
    "bulbasaur": {"species_id": "PKMN-001", "name": "Bulbasaur"},
    "charmander": {"species_id": "PKMN-004", "name": "Charmander"},
    "squirtle": {"species_id": "PKMN-007", "name": "Squirtle"},
}
RIVAL_PICK = {
    "PKMN-001": "PKMN-004",
    "PKMN-004": "PKMN-007",
    "PKMN-007": "PKMN-001",
}
SPECIES_NAMES = {row["species_id"]: row["name"] for row in STARTERS.values()}


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


def _room_id(actor):
    room = getattr(actor, "location", None) if actor else None
    return _text(getattr(getattr(room, "db", None), "room_id", ""))


def _tutorial_defaults():
    return {
        "build": TUTORIAL_BUILD,
        "stage": "MEET_OAK",
        "starter_id": "",
        "starter_slot": None,
        "rival_starter_id": "",
        "battle_id": "",
        "outcome": "",
        "completed": False,
    }


def _write_state(actor, state):
    state = dict(state or {})
    state["build"] = TUTORIAL_BUILD
    actor.db.pokerol_tutorial = deepcopy(state)
    return state


def _find_npc(npc_id):
    wanted = _text(npc_id)
    if not wanted:
        return None
    for obj in ObjectDB.objects.all():
        if _text(getattr(obj.db, "npc_id", "")) == wanted:
            return obj
    return None


def _tutorial_npc_in_room(actor, npc_id):
    room = getattr(actor, "location", None) if actor else None
    if not room:
        return None
    for obj in list(getattr(room, "contents", []) or []):
        if _text(getattr(obj.db, "npc_id", "")) == npc_id:
            return obj
    return None


def _set_if_empty(obj, field, value):
    current = getattr(obj.db, field, None)
    if current in (None, "", [], {}):
        setattr(obj.db, field, deepcopy(value))


def _set_if_missing(obj, field, value):
    if getattr(obj.db, field, None) is None:
        setattr(obj.db, field, deepcopy(value))


def _ensure_one_npc(room, *, npc_id, key, desc, greeting, activity, scene_x, scene_y):
    npc = _find_npc(npc_id)
    created = npc is None
    if created:
        npc = create_object("typeclasses.npcs.NPC", key=key, location=room)
        npc.db.npc_id = npc_id
    elif getattr(npc, "location", None) is not room:
        npc.location = room

    _set_if_empty(npc, "desc", desc)
    _set_if_empty(npc, "dialogue_greeting", greeting)
    _set_if_empty(npc, "current_activity", activity)
    _set_if_empty(npc, "canon_status", "prototype")
    _set_if_missing(npc, "scene_x", float(scene_x))
    _set_if_missing(npc, "scene_y", float(scene_y))
    _set_if_missing(npc, "scene_scale", 1.0)
    return npc


def ensure_tutorial_world(actor):
    """Materialize Oak and Rival only when the player is actually in Oak's lab.

    Existing sprite, position, scale, name and authored text are preserved.
    """
    if _room_id(actor) != LAB_ROOM_ID:
        return {}
    room = getattr(actor, "location", None)
    if not room:
        return {}

    oak = _ensure_one_npc(
        room,
        npc_id=OAK_NPC_ID,
        key="Profesor Oak",
        desc="El Profesor Oak dirige el laboratorio de Pueblo Paleta y estudia la relación entre Pokémon y entrenadores.",
        greeting="Llegaste justo a tiempo. Antes de partir necesitas escoger a tu primer Pokémon.",
        activity="revisando las Poké Balls preparadas para nuevos entrenadores",
        scene_x=68,
        scene_y=7,
    )
    rival = _ensure_one_npc(
        room,
        npc_id=RIVAL_NPC_ID,
        key="Rival",
        desc="Otro joven entrenador de Pueblo Paleta espera junto a la mesa de Poké Balls, impaciente por comenzar.",
        greeting="Por fin llegas. Escoge de una vez; yo elegiré después de ti.",
        activity="esperando junto a las Poké Balls del laboratorio",
        scene_x=38,
        scene_y=7,
    )
    return {"oak": oak, "rival": rival}


def _heal_tutorial_starter(actor, state):
    slot = state.get("starter_slot")
    if slot is None:
        return False
    profile = battle_profile_for_slot(actor, slot)
    if not profile:
        return False
    profile = deepcopy(profile)
    profile["hp_current"] = profile.get("hp_max", profile.get("hp_current", 1))
    profile["status"] = "OK"
    profile["status_turns"] = 0
    return bool(set_party_slot_profile(actor, slot, profile).get("accepted"))


def tutorial_state(actor, *, reconcile=True):
    state = _tutorial_defaults()
    state.update(_dict(getattr(actor.db, "pokerol_tutorial", {})) if actor else {})
    state["build"] = TUTORIAL_BUILD

    if reconcile and state.get("stage") == "BATTLE":
        battle = current_battle(actor)
        if _text(battle.get("status")).upper() != "ACTIVE":
            last = _dict(getattr(actor.db, "last_pokemon_battle", {}))
            if _text(last.get("source_event_id")) == TUTORIAL_BATTLE_SOURCE:
                outcome = _text(last.get("outcome")).upper()
                state["outcome"] = outcome
                if outcome in {"PLAYER_WIN", "PLAYER_LOSS", "DRAW"}:
                    state["stage"] = "COMPLETE"
                    state["completed"] = True
                    _heal_tutorial_starter(actor, state)
                else:
                    state["stage"] = "RIVAL_CHALLENGE"
                    state["battle_id"] = ""
                _write_state(actor, state)
    return state


def _emit_dialogue(actor, speaker, text):
    if not actor:
        return
    actor.msg(
        pokerol_tutorial_dialogue=(({
            "build": TUTORIAL_BUILD,
            "speaker": _text(speaker) or "NARRADOR",
            "text": _text(text),
        },), {})
    )


def _npc_label(actor, npc_id, fallback):
    npc = _tutorial_npc_in_room(actor, npc_id)
    return str(npc.key) if npc else fallback


def tutorial_context_actions(actor):
    if _room_id(actor) != LAB_ROOM_ID:
        return []
    ensure_tutorial_world(actor)
    state = tutorial_state(actor)
    oak_name = _npc_label(actor, OAK_NPC_ID, "Profesor Oak")
    rival_name = _npc_label(actor, RIVAL_NPC_ID, "Rival")

    rows = [
        {"id": "TUTORIAL:OAK", "kind": "INTERACTION", "label": f"Hablar con {oak_name}", "command": "tutorial-oak", "target": oak_name},
        {"id": "TUTORIAL:RIVAL", "kind": "INTERACTION", "label": f"Hablar con {rival_name}", "command": "tutorial-rival", "target": rival_name},
    ]
    if state.get("stage") == "CHOOSE_STARTER":
        for slug in ("bulbasaur", "charmander", "squirtle"):
            rows.append({
                "id": "TUTORIAL:STARTER:" + slug.upper(),
                "kind": "TUTORIAL",
                "label": "ELEGIR " + STARTERS[slug]["name"].upper(),
                "command": "tutorial-elegir " + slug,
                "target": "Poké Balls de Oak",
            })
    if state.get("stage") == "RIVAL_CHALLENGE":
        rows.append({
            "id": "TUTORIAL:RIVAL:BATTLE",
            "kind": "TUTORIAL",
            "label": "ACEPTAR RETO",
            "command": "tutorial-reto",
            "target": rival_name,
        })
    return rows


def talk_oak(actor):
    if _room_id(actor) != LAB_ROOM_ID:
        return {"accepted": False, "status": "OAK_NOT_HERE", "build": TUTORIAL_BUILD}
    npcs = ensure_tutorial_world(actor)
    state = tutorial_state(actor)
    oak = npcs.get("oak")
    oak_name = str(oak.key) if oak else "Profesor Oak"
    stage = _text(state.get("stage")).upper()

    if stage == "MEET_OAK":
        state["stage"] = "CHOOSE_STARTER"
        _write_state(actor, state)
        greeting = _text(getattr(getattr(oak, "db", None), "dialogue_greeting", "")) if oak else ""
        intro = greeting or "Llegaste justo a tiempo. Antes de partir necesitas escoger a tu primer Pokémon."
        _emit_dialogue(actor, oak_name, intro + " Sobre la mesa tienes a Bulbasaur, Charmander y Squirtle. Elige uno.")
    elif stage == "CHOOSE_STARTER":
        _emit_dialogue(actor, oak_name, "Los tres están listos. Bulbasaur, Charmander o Squirtle: la decisión es tuya.")
    elif stage == "RIVAL_CHALLENGE":
        _emit_dialogue(actor, oak_name, "Ya tienes compañero. Ahora aprende a darle órdenes: tu rival quiere probarte aquí mismo.")
    elif stage == "BATTLE":
        _emit_dialogue(actor, oak_name, "Concéntrate en tu Pokémon y observa lo que hace el rival. Esta es tu primera batalla como entrenador.")
    else:
        _emit_dialogue(actor, oak_name, "Bien hecho. Ganar o perder era secundario: ya diste el primer paso como entrenador Pokémon.")
    return {"accepted": True, "status": "OAK_TALKED", "state": state, "build": TUTORIAL_BUILD}


def talk_rival(actor):
    if _room_id(actor) != LAB_ROOM_ID:
        return {"accepted": False, "status": "RIVAL_NOT_HERE", "build": TUTORIAL_BUILD}
    ensure_tutorial_world(actor)
    state = tutorial_state(actor)
    rival_name = _npc_label(actor, RIVAL_NPC_ID, "Rival")
    stage = _text(state.get("stage")).upper()

    if stage in {"MEET_OAK", "CHOOSE_STARTER"}:
        _emit_dialogue(actor, rival_name, "Apúrate. Tú eliges primero; yo sabré cuál tomar después.")
    elif stage == "RIVAL_CHALLENGE":
        chosen = SPECIES_NAMES.get(_text(state.get("rival_starter_id")), "mi Pokémon")
        _emit_dialogue(actor, rival_name, f"Yo me quedo con {chosen}. Ya que ambos tenemos Pokémon, ¡vamos a ver quién sabe usarlos mejor!")
    elif stage == "BATTLE":
        _emit_dialogue(actor, rival_name, "¡Nada de echarte atrás ahora! La batalla ya empezó.")
    else:
        outcome = _text(state.get("outcome")).upper()
        if outcome == "PLAYER_WIN":
            line = "Tch... esta vez ganaste. La próxima no te lo voy a dejar tan fácil."
        elif outcome == "PLAYER_LOSS":
            line = "¿Ves? Tener un Pokémon no basta. Tendrás que entrenar si quieres alcanzarme."
        else:
            line = "Eso estuvo más parejo de lo que esperaba. La próxima lo resolvemos de verdad."
        _emit_dialogue(actor, rival_name, line)
    return {"accepted": True, "status": "RIVAL_TALKED", "state": state, "build": TUTORIAL_BUILD}


def _fallback_move(move_id, name, *, damage_class="PHYSICAL", power=40, accuracy=100, pp=35):
    return {
        "move_id": move_id,
        "name": name,
        "pokemon_type": "Normal",
        "damage_class": damage_class,
        "power": power,
        "accuracy": accuracy,
        "priority": 0,
        "pp": pp,
        "pp_max": pp,
        "pp_current": pp,
        "world_enabled": False,
        "world_effects": [],
        "materials": ["CREATURE"],
        "delivery": "CONTACT",
        "requirements": {},
    }


def _fallback_starter(species_id, *, level=5):
    profiles = {
        "PKMN-001": ("Bulbasaur", ["Grass", "Poison"], {"HP": 45, "ATK": 49, "DEF": 49, "SPA": 65, "SPD": 65, "SPE": 45}, 1),
        "PKMN-004": ("Charmander", ["Fire"], {"HP": 39, "ATK": 52, "DEF": 43, "SPA": 60, "SPD": 50, "SPE": 65}, 4),
        "PKMN-007": ("Squirtle", ["Water"], {"HP": 44, "ATK": 48, "DEF": 65, "SPA": 50, "SPD": 64, "SPE": 43}, 7),
    }
    row = profiles.get(species_id)
    if not row:
        return None
    name, types, stats, sprite_id = row
    moves = [_fallback_move("TACKLE", "Tackle")]
    if species_id in {"PKMN-001", "PKMN-004"}:
        moves.append(_fallback_move("GROWL", "Growl", damage_class="STATUS", power=0, pp=40))
    else:
        moves.append(_fallback_move("TAIL-WHIP", "Tail Whip", damage_class="STATUS", power=0, pp=30))
    return {
        "species_id": species_id,
        "species_name": name,
        "level": int(level),
        "types": types,
        "base_stats": stats,
        "moves": moves,
        "resolved_moves": deepcopy(moves),
        "sprite": {
            "front": f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{sprite_id}.png",
            "back": f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/back/{sprite_id}.png",
            "icon": f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{sprite_id}.png",
            "scale": 1.25,
        },
        "wild": False,
        "status": "OK",
    }


def _starter_profile(species_id, *, level=5):
    return spawn_species_profile(species_id, level=level, wild=False) or _fallback_starter(species_id, level=level)


def choose_starter(actor, choice):
    if _room_id(actor) != LAB_ROOM_ID:
        return {"accepted": False, "status": "NOT_IN_OAK_LAB", "build": TUTORIAL_BUILD}
    ensure_tutorial_world(actor)
    state = tutorial_state(actor)
    if state.get("stage") != "CHOOSE_STARTER":
        return {"accepted": False, "status": "STARTER_NOT_AVAILABLE", "state": state, "build": TUTORIAL_BUILD}

    raw = _text(choice).lower()
    aliases = {
        "pkmn-001": "bulbasaur", "001": "bulbasaur", "1": "bulbasaur",
        "pkmn-004": "charmander", "004": "charmander", "4": "charmander",
        "pkmn-007": "squirtle", "007": "squirtle", "7": "squirtle",
    }
    slug = raw if raw in STARTERS else aliases.get(raw, "")
    if not slug:
        return {"accepted": False, "status": "INVALID_STARTER", "build": TUTORIAL_BUILD}

    party = party_state(actor).get("party") or []
    if len(party) >= 6:
        _emit_dialogue(actor, "Profesor Oak", "Tu equipo está lleno. Necesito que tengas un espacio libre antes de entregarte el Pokémon del tutorial.")
        return {"accepted": False, "status": "PARTY_FULL", "build": TUTORIAL_BUILD}

    starter_id = STARTERS[slug]["species_id"]
    profile = _starter_profile(starter_id, level=5)
    if not profile:
        return {"accepted": False, "status": "STARTER_PROFILE_MISSING", "species_id": starter_id, "build": TUTORIAL_BUILD}
    added = add_pokemon(actor, profile, prefer_party=True)
    if not added.get("accepted"):
        return {"accepted": False, "status": added.get("status"), "build": TUTORIAL_BUILD}
    slot = added.get("slot")
    set_active_slot(actor, slot, require_able=True)

    rival_id = RIVAL_PICK[starter_id]
    state.update({
        "stage": "RIVAL_CHALLENGE",
        "starter_id": starter_id,
        "starter_slot": slot,
        "rival_starter_id": rival_id,
        "battle_id": "",
        "outcome": "",
        "completed": False,
    })
    _write_state(actor, state)

    starter_name = SPECIES_NAMES.get(starter_id, starter_id)
    rival_name = SPECIES_NAMES.get(rival_id, rival_id)
    _emit_dialogue(actor, _npc_label(actor, OAK_NPC_ID, "Profesor Oak"), f"Entonces {starter_name} será tu compañero. Trátalo bien y aprende a trabajar con él.")
    _emit_dialogue(actor, _npc_label(actor, RIVAL_NPC_ID, "Rival"), f"Perfecto. Entonces yo elijo a {rival_name}. ¡Ahora que ambos tenemos Pokémon, te reto a una batalla!")
    return {"accepted": True, "status": "STARTER_CHOSEN", "state": state, "pokemon": added.get("pokemon"), "build": TUTORIAL_BUILD}


def start_rival_battle(actor):
    if _room_id(actor) != LAB_ROOM_ID:
        return {"accepted": False, "status": "NOT_IN_OAK_LAB", "build": TUTORIAL_BUILD}
    ensure_tutorial_world(actor)
    state = tutorial_state(actor)
    if state.get("stage") != "RIVAL_CHALLENGE":
        return {"accepted": False, "status": "RIVAL_CHALLENGE_NOT_READY", "state": state, "build": TUTORIAL_BUILD}

    slot = state.get("starter_slot")
    if slot is None:
        return {"accepted": False, "status": "STARTER_SLOT_MISSING", "build": TUTORIAL_BUILD}
    active = set_active_slot(actor, slot, require_able=True)
    if not active.get("accepted"):
        return {"accepted": False, "status": active.get("status"), "build": TUTORIAL_BUILD}
    player = battle_profile_for_slot(actor, slot)
    rival_id = _text(state.get("rival_starter_id"))
    enemy = _starter_profile(rival_id, level=5)
    if not player or not enemy:
        return {"accepted": False, "status": "BATTLE_PROFILE_MISSING", "build": TUTORIAL_BUILD}

    enemy = deepcopy(enemy)
    enemy["wild"] = False
    enemy["owner_id"] = RIVAL_NPC_ID
    _emit_dialogue(actor, _npc_label(actor, RIVAL_NPC_ID, "Rival"), f"¡Vamos, {SPECIES_NAMES.get(rival_id, 'Pokémon')}! ¡Muéstrale lo que podemos hacer!")
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
        _write_state(actor, state)
    return {**result, "tutorial_state": state, "build": TUTORIAL_BUILD}
