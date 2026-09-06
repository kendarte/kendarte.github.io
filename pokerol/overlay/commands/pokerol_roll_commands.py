from evennia import Command
from services.player_roll_resolution_engine import PLAYER_ROLL_BUILD, resolve_pending_object_action_roll


class CmdPokerolRoll(Command):
    key = "tirar"
    aliases = ["roll", "pokerol-roll"]
    locks = "cmd:all()"

    def func(self):
        packet = resolve_pending_object_action_roll(self.caller)
        status = str(packet.get("status") or "")
        if status == "NO_PENDING_OBJECT_ACTION":
            self.caller.msg("No tienes ninguna acción pendiente de tirada.")
            return
        if status == "UNSUPPORTED_MODE":
            self.caller.msg(f"Modo de tirada no soportado: {packet.get('mode')}.")
            return
        if status != "RESOLVED":
            self.caller.msg(f"[TIRADA BLOQUEADA] status={status} | build={PLAYER_ROLL_BUILD}")
            return
        mode = str(packet.get("mode") or "").upper()
        outcome = packet.get("outcome")
        if mode == "CONFRONT":
            self.caller.msg(
                f"[CONFRONT] tú={packet.get('actor_total')} | {packet.get('target_name')}={packet.get('target_total')} | {outcome}"
            )
        elif mode == "SYNCHRONIZE":
            self.caller.msg(
                f"[SYNCHRONIZE] actor={packet.get('actor_total')} | target={packet.get('target_total')} | {outcome}"
            )
        else:
            self.caller.msg(
                f"[ROLL] mode={mode} | die={packet.get('die')} | total={packet.get('total')} | outcome={outcome}"
            )
