from evennia import Command

from services.player_roll_resolution_engine import PLAYER_ROLL_BUILD, resolve_pending_object_action_roll
from world.upgrade_pilot_v55 import reset_v55_playtest_state


def _parity_es(value):
    return "PAR" if str(value or "").upper() == "EVEN" else "IMPAR"


class CmdSizaRollV55(Command):
    """Resolve the caller's latest DIRECT, ACCUMULATE, CONFRONT or SYNCHRONIZE object action."""

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

        if mode == "SYNCHRONIZE":
            self.caller.msg(
                f"[SINCRONIA] d6={packet.get('die')} + {packet.get('actor_stat')}={packet.get('actor_stat_value')} "
                f"=> {packet.get('total')} ({_parity_es(packet.get('result_parity'))}) | "
                f"objetivo={_parity_es(packet.get('required_parity'))} | {packet.get('outcome')}"
            )
            return

        base = (
            f"[TIRADA] d6={packet.get('die')} + {packet.get('actor_stat')}={packet.get('actor_stat_value')} "
            f"=> {packet.get('total')} | dificultad={packet.get('difficulty')} | {packet.get('outcome')}"
        )
        if mode == "ACCUMULATE":
            base += f" | progreso={packet.get('progress_after')}/{packet.get('progress_goal')}"
        self.caller.msg(base)


class CmdSizaResetV55(Command):
    """Reset only the v0.55 synchronize prototype state."""

    key = "siza-reset-v55"
    aliases = ["reset-v55"]
    locks = "cmd:perm(Admin)"

    def func(self):
        result = reset_v55_playtest_state()
        if not result.get("success"):
            self.caller.msg(
                f"[V0.55 RESET] FAIL | reason={result.get('reason')} | build={PLAYER_ROLL_BUILD}"
            )
            return
        manifest = result.get("manifest")
        self.caller.msg(f"=== SIZA v0.55 RESET | {PLAYER_ROLL_BUILD} ===")
        self.caller.msg(
            f"PASS synchronize playtest reset | manifest={manifest.key}#{manifest.id} | synced=False | objetivo=PAR"
        )
        self.caller.msg("Pista de sincronizacion visible=False")
        self.caller.msg("No se tocaron estados v0.51-v0.54, jobs, NPCs, exits, skills ni Knowledge.")
        self.caller.msg("========================================================")
