from evennia import Command

from services.pokemon_battle_tactical_runtime import (
    emit_reaction_options,
    set_player_reaction,
)


class CmdPokerolReactionOptions(Command):
    key = "pokerol-reaction-options"
    aliases = ["reacciones-batalla"]
    locks = "cmd:all()"

    def func(self):
        result = emit_reaction_options(self.caller)
        if not result.get("accepted"):
            self.caller.msg(f"Reacciones no disponibles: {result.get('status')}")


class CmdPokerolBattleReaction(Command):
    key = "pokerol-reaction"
    aliases = ["reaccion-batalla", "reacción-batalla"]
    locks = "cmd:all()"

    def func(self):
        parts = str(self.args or "DODGE").strip().split()
        policy = (parts[0] if parts else "DODGE").upper()
        method_move_id = parts[1] if len(parts) > 1 else ""
        result = set_player_reaction(self.caller, policy, method_move_id=method_move_id)
        if not result.get("accepted"):
            self.caller.msg(f"Reacción rechazada: {result.get('status')}")
