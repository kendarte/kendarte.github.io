from evennia import Command

from services.pokemon_battle_tactical_runtime import (
    emit_reaction_options,
    submit_reaction_window_choice,
)


class CmdPokerolReactionOptions(Command):
    key = "pokerol-reaction-options"
    aliases = ["reacciones-batalla"]
    locks = "cmd:all()"

    def func(self):
        result = emit_reaction_options(self.caller)
        if not result.get("accepted"):
            self.caller.msg(f"Reacción no disponible: {result.get('status')}")


class CmdPokerolBattleReaction(Command):
    key = "pokerol-reaction"
    aliases = ["reaccion-batalla", "reacción-batalla"]
    locks = "cmd:all()"

    def func(self):
        parts = str(self.args or "").strip().split()
        if len(parts) < 2:
            self.caller.msg("No hay una respuesta de ventana válida.")
            return
        window_id = parts[0]
        policy = parts[1].upper()
        method_move_id = parts[2] if len(parts) > 2 else ""
        result = submit_reaction_window_choice(
            self.caller,
            window_id,
            policy=policy,
            method_move_id=method_move_id,
        )
        if not result.get("accepted"):
            self.caller.msg(f"Reacción rechazada: {result.get('status')}")
