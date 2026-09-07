from evennia import Command

from services.pokerol_event_editor_service import OAK_TUTORIAL_EVENT_ID, get_room_event
from services.pokerol_player_progress import record_event
from services.pokerol_tutorial_engine import (
    LAB_ROOM_ID,
    SPECIES_NAMES,
    choose_starter,
    start_rival_battle,
    talk_oak,
    talk_rival,
    tutorial_state,
)

OAK_PORTRAIT = "https://play.pokemonshowdown.com/sprites/trainers/oak.png"
RIVAL_PORTRAIT = "https://play.pokemonshowdown.com/sprites/trainers/blue.png"
STARTER_MEDIA = {
    "bulbasaur": {
        "species_id": "PKMN-001",
        "name": "Bulbasaur",
        "types": ["PLANTA", "VENENO"],
        "image": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/1.png",
    },
    "charmander": {
        "species_id": "PKMN-004",
        "name": "Charmander",
        "types": ["FUEGO"],
        "image": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/4.png",
    },
    "squirtle": {
        "species_id": "PKMN-007",
        "name": "Squirtle",
        "types": ["AGUA"],
        "image": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/7.png",
    },
}


def _refresh(actor):
    from commands.pokerol_ui_runtime_commands import emit_room_snapshot

    emit_room_snapshot(actor, visible_text=False)


def _room_id(actor):
    room = getattr(actor, "location", None)
    return str(getattr(getattr(room, "db", None), "room_id", "") or "").strip()


def _slug(value):
    raw = str(value or "").strip().lower()
    aliases = {
        "pkmn-001": "bulbasaur", "001": "bulbasaur", "1": "bulbasaur",
        "pkmn-004": "charmander", "004": "charmander", "4": "charmander",
        "pkmn-007": "squirtle", "007": "squirtle", "7": "squirtle",
    }
    return raw if raw in STARTER_MEDIA else aliases.get(raw, "")


def _event_settings(actor):
    room = getattr(actor, "location", None)
    event = get_room_event(room, OAK_TUTORIAL_EVENT_ID) if room else None
    settings = dict((event or {}).get("settings") or {})
    return event or {}, settings


def _flags(actor):
    try:
        return dict(getattr(actor.db, "pokerol_flags", None) or {})
    except Exception:
        return {}


def _write_flags(actor, **updates):
    flags = _flags(actor)
    flags.update(updates)
    actor.db.pokerol_flags = flags


def _progress_markers(actor):
    try:
        return dict(getattr(actor.db, "pokerol_tutorial_progress_markers", None) or {})
    except Exception:
        return {}


def _set_progress_marker(actor, key, value=True):
    rows = _progress_markers(actor)
    rows[str(key)] = value
    actor.db.pokerol_tutorial_progress_markers = rows


def _emit_modal(actor, packet):
    actor.msg(
        pokerol_event_modal=(({
            "event_id": OAK_TUTORIAL_EVENT_ID,
            "blocking": True,
            **dict(packet or {}),
        },), {})
    )


def _starter_choice_allowed(actor, slug):
    event, settings = _event_settings(actor)
    if not event or not bool(event.get("enabled", True)):
        return False
    configured = [
        str(value or "").strip().lower()
        for value in list(settings.get("starter_choices") or ["bulbasaur", "charmander", "squirtle"])
    ]
    return slug in configured


def _record_starter(actor, state):
    starter_id = str(state.get("starter_id") or "")
    rival_id = str(state.get("rival_starter_id") or "")
    marker = "starter:" + starter_id
    if _progress_markers(actor).get(marker):
        return

    starter_name = SPECIES_NAMES.get(starter_id, starter_id or "Pokémon")
    rival_name = SPECIES_NAMES.get(rival_id, rival_id or "Pokémon")
    media = next((row for row in STARTER_MEDIA.values() if row["species_id"] == starter_id), {})
    record_event(
        actor,
        event_id=OAK_TUTORIAL_EVENT_ID + ":STARTER",
        title="Mi primer Pokémon",
        result="Elegí a {}. El rival eligió a {}.".format(starter_name, rival_name),
        room_id=LAB_ROOM_ID,
        data={"starter_id": starter_id, "rival_starter_id": rival_id},
        create_memory=True,
        memory_text="El Profesor Oak me entregó a {} como mi primer compañero. Mi rival eligió a {}.".format(
            starter_name, rival_name
        ),
        memory_image=str(media.get("image") or ""),
    )
    _write_flags(
        actor,
        oak_intro_done=True,
        starter_chosen=True,
        starter_id=starter_id,
        rival_starter_id=rival_id,
        rival_starter_taken=True,
    )
    _set_progress_marker(actor, marker)


def _record_battle_start(actor, state):
    battle_id = str(state.get("battle_id") or "")
    marker = "battle-start:" + (battle_id or "tutorial")
    if _progress_markers(actor).get(marker):
        return
    record_event(
        actor,
        event_id=OAK_TUTORIAL_EVENT_ID + ":RIVAL-CHALLENGE",
        title="Primer reto del rival",
        result="La primera batalla contra el rival comenzó.",
        room_id=LAB_ROOM_ID,
        data={
            "battle_id": battle_id,
            "starter_id": state.get("starter_id"),
            "rival_starter_id": state.get("rival_starter_id"),
        },
        create_memory=False,
    )
    _write_flags(actor, rival_challenge_started=True)
    _set_progress_marker(actor, marker)


def _record_battle_finish(actor, state):
    if not bool(state.get("completed")):
        return False
    outcome = str(state.get("outcome") or "").upper()
    marker = "battle-finish:" + (outcome or "UNKNOWN")
    if _progress_markers(actor).get(marker):
        return True

    label = {
        "PLAYER_WIN": "Gané mi primera batalla contra el rival.",
        "PLAYER_LOSS": "Perdí mi primera batalla contra el rival.",
        "DRAW": "Mi primera batalla contra el rival terminó en empate.",
    }.get(outcome, "Mi primera batalla contra el rival terminó.")

    record_event(
        actor,
        event_id=OAK_TUTORIAL_EVENT_ID + ":FIRST-BATTLE",
        title="Mi primera batalla",
        result=outcome or "COMPLETE",
        room_id=LAB_ROOM_ID,
        data={
            "outcome": outcome,
            "starter_id": state.get("starter_id"),
            "rival_starter_id": state.get("rival_starter_id"),
        },
        create_memory=True,
        memory_text=label,
    )
    _write_flags(
        actor,
        rival_battle_done=True,
        rival_battle_outcome=outcome,
        oak_tutorial_complete=True,
    )
    _set_progress_marker(actor, marker)
    return True


def _preview(actor, raw_choice):
    slug = _slug(raw_choice)
    state = tutorial_state(actor)
    if _room_id(actor) != LAB_ROOM_ID or state.get("stage") != "CHOOSE_STARTER":
        return False
    if not slug or not _starter_choice_allowed(actor, slug):
        return False
    row = STARTER_MEDIA[slug]
    _emit_modal(
        actor,
        {
            "modal_id": "STARTER:" + slug.upper(),
            "kind": "STARTER_PREVIEW",
            "title": row["name"],
            "speaker": "PROF. OAK",
            "text": "¿Quieres que {} sea tu primer Pokémon?".format(row["name"]),
            "media_type": "image",
            "media_src": row["image"],
            "caption": "TIPO · " + " / ".join(row["types"]),
            "buttons": [
                {
                    "label": "TOMAR A " + row["name"].upper(),
                    "command": "tutorial-elegir confirm:" + slug,
                    "primary": True,
                },
                {"label": "CANCELAR", "close": True},
            ],
        },
    )
    return True


class CmdPokerolTutorialOak(Command):
    key = "tutorial-oak"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        mode = str(self.args or "").strip().lower()
        if mode == "finalize":
            _record_battle_finish(self.caller, tutorial_state(self.caller))
            _refresh(self.caller)
            return
        talk_oak(self.caller)
        _refresh(self.caller)


class CmdPokerolTutorialRival(Command):
    key = "tutorial-rival"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        talk_rival(self.caller)
        _refresh(self.caller)


class CmdPokerolTutorialChooseStarter(Command):
    key = "tutorial-elegir"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        raw = str(self.args or "").strip()
        if raw.lower().startswith("confirm:"):
            choice = raw.split(":", 1)[1]
            result = choose_starter(self.caller, choice)
            if result.get("accepted") and result.get("status") == "STARTER_CHOSEN":
                _record_starter(self.caller, dict(result.get("state") or tutorial_state(self.caller)))
            elif result.get("status") not in {"PARTY_FULL"}:
                self.caller.msg("No se pudo elegir ese Pokémon: {}".format(result.get("status")))
            _refresh(self.caller)
            return

        if not _preview(self.caller, raw):
            self.caller.msg("No se pudo abrir esa Poké Ball.")
        _refresh(self.caller)


class CmdPokerolTutorialRivalChallenge(Command):
    key = "tutorial-reto"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        result = start_rival_battle(self.caller)
        if result.get("accepted"):
            state = dict(result.get("tutorial_state") or tutorial_state(self.caller, reconcile=False))
            _record_battle_start(self.caller, state)
        else:
            self.caller.msg("No se pudo iniciar la batalla: {}".format(result.get("status")))
            _refresh(self.caller)
