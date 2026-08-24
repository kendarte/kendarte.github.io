from evennia import Command

from services.player_roll_resolution_engine import PLAYER_ROLL_BUILD, resolve_pending_object_action_roll
from world.upgrade_pilot_v54 import reset_v54_playtest_state


class CmdSizaRollV54(Command):
    """Resolve the caller's latest DIRECT, ACCUMULATE or CONFRONT object action."""

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
        if mode == "CONFRONT":
            self.caller.msg(
                f"[CONFRONT] tu d6={packet.get('actor_die')} + {packet.get('actor_stat')}={packet.get('actor_stat_value')} "
                f"=> {packet.get('actor_total')} | {packet.get('target_name')} d6={packet.get('target_die')} + "
                f"{packet.get('target_stat')}={packet.get('target_stat_value')} => {packet.get('target_total')} | "
                f"{packet.get('outcome')}"
            )
            return

        base = (
            f"[TIRADA] d6={packet.get('die')} + {packet.get('actor_stat')}={packet.get('actor_stat_value')} "
            f"=> {packet.get('total')} | dificultad={packet.get('difficulty')} | {packet.get('outcome')}"
        )
        if mode == "ACCUMULATE":
            base += f" | progreso={packet.get('progress_after')}/{packet.get('progress_goal')}"
        self.caller.msg(base)


class CmdSizaResetV54(Command):
    """Reset only the v0.54 confront prototype state."""

    key = "siza-reset-v54"
    aliases = ["reset-v54"]
    locks = "cmd:perm(Admin)"

    def func(self):
        result = reset_v54_playtest_state()
        if not result.get("success"):
            self.caller.msg(
                f"[V0.54 RESET] FAIL | reason={result.get('reason')} | build={PLAYER_ROLL_BUILD}"
            )
            return
        target = result.get("target")
        self.caller.msg(f"=== SIZA v0.54 RESET | {PLAYER_ROLL_BUILD} ===")
        self.caller.msg(
            f"PASS confront playtest reset | target={target.key}#{target.id} | cedio=False | "
            f"{result.get('target_stat')}={result.get('target_stat_value')}"
        )
        self.caller.msg("Pista de confrontacion visible=False")
        self.caller.msg("No se tocaron estados v0.51-v0.53, jobs, exits, skills ni Knowledge.")
        self.caller.msg("========================================================")
