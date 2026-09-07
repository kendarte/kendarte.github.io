from evennia import Command

from services.pokerol_player_progress import PLAYER_PROGRESS_BUILD, player_sheet_state


class CmdPokerolPlayerSheet(Command):
    key = "pokerol-player-sheet"
    aliases = ("ficha-entrenador", "trainer-sheet")
    locks = "cmd:all()"
    help_category = "POKEROL"

    def func(self):
        packet = player_sheet_state(self.caller)
        packet["build"] = PLAYER_PROGRESS_BUILD
        self.caller.msg(pokerol_player_sheet=((packet,), {}))
