from evennia import Command

from services.pokemon_battle_tactical_runtime import set_player_reaction


class CmdPokerolBattleReaction(Command):
    key = "pokerol-reaction"
    aliases = ["reaccion-batalla", "reacción-batalla"]
    locks = "cmd:all()"

    def func(self):
        policy = str(self.args or "DODGE").strip().upper() or "DODGE"
        result = set_player_reaction(self.caller, policy)
        if not result.get("accepted"):
            self.caller.msg(f"Reacción rechazada: {result.get('status')}")
