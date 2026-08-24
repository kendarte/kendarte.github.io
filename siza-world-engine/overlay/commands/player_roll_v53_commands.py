from evennia import Command

from services.player_roll_resolution_engine import PLAYER_ROLL_BUILD, resolve_pending_object_action_roll
from world.upgrade_pilot_v53 import reset_v53_playtest_state


class CmdSizaRollV53(Command):
    """Resolve the caller's latest pending DIRECT or ACCUMULATE object action."""

    key = "tirar"
    aliases = ["roll", "siza-roll"]
    locks = "cmd:all()"

    def func(self):
        packet = resolve_pending_object_action_roll(self.caller)
        status = str(packet.get("status") or "")
        if status == "NO_PENDING_OBJECT_ACTION":
            self.caller.msg("No tienes ninguna accion de objeto pendiente de tirada.")
            return
        if status == "UNSUPPORTED_MODE":
            self.caller.msg(
                f"Esta tirada usa un modo aun no soportado por el player roll: {packet.get('mode')}."
            )
            return
        if status != "RESOLVED":
            self.caller.msg(
                f"[TIRADA BLOQUEADA] status={status} | build={PLAYER_ROLL_BUILD}"
            )
            return

        mode = str(packet.get("mode") or "").upper()
        base = (
            f"[TIRADA] d6={packet.get('die')} + {packet.get('actor_stat')}={packet.get('actor_stat_value')} "
            f"=> {packet.get('total')} | dificultad={packet.get('difficulty')} | {packet.get('outcome')}"
        )
        if mode == "ACCUMULATE":
            base += (
                f" | progreso={packet.get('progress_after')}/{packet.get('progress_goal')}"
            )
        self.caller.msg(base)


class CmdSizaResetV53(Command):
    """Reset only the v0.53 accumulated reconstruction prototype state."""

    key = "siza-reset-v53"
    aliases = ["reset-v53"]
    locks = "cmd:perm(Admin)"

    def func(self):
        result = reset_v53_playtest_state()
        if not result.get("success"):
            self.caller.msg(
                f"[V0.53 RESET] FAIL | reason={result.get('reason')} | build={PLAYER_ROLL_BUILD}"
            )
            return
        manifest = result.get("manifest")
        self.caller.msg(f"=== SIZA v0.53 RESET | {PLAYER_ROLL_BUILD} ===")
        self.caller.msg(
            f"PASS accumulate playtest reset | manifest={manifest.key}#{manifest.id} | progreso=0/{result.get('goal')} | complete=False"
        )
        self.caller.msg("Pista de secuencia reconstruida visible=False")
        self.caller.msg("No se tocaron estados de v0.51/v0.52, jobs, NPCs, exits, skills ni Knowledge.")
        self.caller.msg("========================================================")
