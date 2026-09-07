from evennia import Command

from services.pokerol_event_editor_service import OAK_TUTORIAL_EVENT_ID, get_room_event
from services.pokerol_tutorial_engine import (
    LAB_ROOM_ID,
    choose_starter,
    start_rival_battle,
    talk_oak,
    talk_rival,
    tutorial_state,
)
from services.pokerol_tutorial_progress import (
    mark_oak_battle_started,
    reconcile_oak_progress,
    resume_oak_event,
    snooze_oak_event,
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


def _preview(actor, raw_choice):
    slug = _slug(raw_choice)
    state = reconcile_oak_progress(actor)
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

        if mode in {"sync", "finalize"}:
            reconcile_oak_progress(self.caller)
            _refresh(self.caller)
            return

        if mode == "snooze":
            snooze_oak_event(self.caller)
            _refresh(self.caller)
            return

        state = reconcile_oak_progress(self.caller)
        if state.get("completed"):
            if mode not in {"enter"}:
                talk_oak(self.caller)
            _refresh(self.caller)
            return

        resume_oak_event(self.caller)
        talk_oak(self.caller)
        _refresh(self.caller)


class CmdPokerolTutorialRival(Command):
    key = "tutorial-rival"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        reconcile_oak_progress(self.caller)
        resume_oak_event(self.caller)
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
            state = reconcile_oak_progress(self.caller)
            if state.get("stage") != "CHOOSE_STARTER":
                if state.get("starter_id"):
                    self.caller.msg("Ya tienes tu primer Pokémon. El evento continúa desde donde quedó guardado.")
                else:
                    self.caller.msg("La elección de starter no está disponible en este momento.")
                _refresh(self.caller)
                return

            resume_oak_event(self.caller)
            result = choose_starter(self.caller, choice)
            if result.get("accepted") and result.get("status") == "STARTER_CHOSEN":
                reconcile_oak_progress(self.caller, dict(result.get("state") or tutorial_state(self.caller)))
            elif result.get("status") not in {"PARTY_FULL"}:
                self.caller.msg("No se pudo elegir ese Pokémon: {}".format(result.get("status")))
            _refresh(self.caller)
            return

        if not _preview(self.caller, raw):
            state = reconcile_oak_progress(self.caller)
            if state.get("starter_id"):
                self.caller.msg("Ya tienes tu primer Pokémon. Esa Poké Ball ya no forma parte del evento activo.")
            else:
                self.caller.msg("No se pudo abrir esa Poké Ball.")
        _refresh(self.caller)


class CmdPokerolTutorialRivalChallenge(Command):
    key = "tutorial-reto"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        state = reconcile_oak_progress(self.caller)
        if state.get("completed"):
            self.caller.msg("Este evento ya está completado.")
            _refresh(self.caller)
            return

        resume_oak_event(self.caller)
        result = start_rival_battle(self.caller)
        if result.get("accepted"):
            state = dict(result.get("tutorial_state") or tutorial_state(self.caller, reconcile=False))
            mark_oak_battle_started(self.caller, state)
        else:
            self.caller.msg("No se pudo iniciar la batalla: {}".format(result.get("status")))
            _refresh(self.caller)
