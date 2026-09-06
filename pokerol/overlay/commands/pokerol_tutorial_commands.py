from evennia import Command

from services.pokerol_tutorial_engine import (
    choose_starter,
    start_rival_battle,
    talk_oak,
    talk_rival,
)


def _refresh(actor):
    from commands.pokerol_ui_runtime_commands import emit_room_snapshot

    emit_room_snapshot(actor, visible_text=False)


class CmdPokerolTutorialOak(Command):
    key = "tutorial-oak"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
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
        result = choose_starter(self.caller, self.args)
        if not result.get("accepted") and result.get("status") not in {"PARTY_FULL"}:
            self.caller.msg("No se pudo elegir ese Pokémon: {}".format(result.get("status")))
        _refresh(self.caller)


class CmdPokerolTutorialRivalChallenge(Command):
    key = "tutorial-reto"
    aliases = ()
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        result = start_rival_battle(self.caller)
        if not result.get("accepted"):
            self.caller.msg("No se pudo iniciar la batalla: {}".format(result.get("status")))
            _refresh(self.caller)
