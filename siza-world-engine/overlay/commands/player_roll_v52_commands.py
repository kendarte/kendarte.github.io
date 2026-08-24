from evennia import Command

from services.action_resolution_engine import (
    adventure_stats,
    normalize_stat_key,
    set_adventure_stat,
)
from services.direct_d6_resolution_engine import (
    DIRECT_D6_BUILD,
    resolve_pending_object_action_d6,
)
from world.upgrade_pilot_v52 import reset_v52_playtest_state


class CmdSizaRoll(Command):
    """Resolve the caller's latest pending DIRECT object action with the Siza d6 provider."""

    key = "tirar"
    aliases = ["roll", "siza-roll"]
    locks = "cmd:all()"

    def func(self):
        packet = resolve_pending_object_action_d6(self.caller)
        status = str(packet.get("status") or "")
        if status == "NO_PENDING_OBJECT_ACTION":
            self.caller.msg("No tienes ninguna accion de objeto pendiente de tirada.")
            return
        if status == "UNSUPPORTED_MODE":
            self.caller.msg(
                f"Esta tirada usa un modo aun no soportado por el provider d6: {packet.get('mode')}."
            )
            return
        if status != "RESOLVED":
            self.caller.msg(
                f"[TIRADA BLOQUEADA] status={status} | build={DIRECT_D6_BUILD}"
            )
            return

        self.caller.msg(
            f"[TIRADA] d6={packet.get('die')} + {packet.get('actor_stat')}={packet.get('actor_stat_value')} "
            f"=> {packet.get('total')} | dificultad={packet.get('difficulty')} | {packet.get('outcome')}"
        )


class CmdSizaSelfStatSet(Command):
    """Admin/playtest: set one Adventure stat on the current Character."""

    key = "siza-self-stat-set"
    aliases = ["self-stat-set"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) != 2:
            self.caller.msg("Uso: siza-self-stat-set <FUE|AGI|COO|INT|PER|PSI> <VALUE>")
            return
        packet = set_adventure_stat(self.caller, parts[0], parts[1])
        if not packet.get("success"):
            self.caller.msg(f"[SELF STAT DENIED] reason={packet.get('reason')}")
            return
        self.caller.msg(
            f"[SELF STAT SET] {packet.get('stat')} | {packet.get('before')} -> {packet.get('after')}"
        )


class CmdSizaSelfStatClear(Command):
    """Admin/playtest: return one Character stat to truly UNSET without touching the others."""

    key = "siza-self-stat-clear"
    aliases = ["self-stat-clear"]
    locks = "cmd:perm(Admin)"

    def func(self):
        stat = normalize_stat_key((self.args or "").strip())
        if not stat:
            self.caller.msg("Uso: siza-self-stat-clear <FUE|AGI|COO|INT|PER|PSI>")
            return
        stats = adventure_stats(self.caller)
        before = stats.pop(stat, None)
        self.caller.db.adventure_stats = stats
        self.caller.msg(f"[SELF STAT CLEAR] {stat} | {before} -> UNSET")


class CmdSizaResetV52(Command):
    """Reset only the v0.52 checked-manifest prototype state."""

    key = "siza-reset-v52"
    aliases = ["reset-v52"]
    locks = "cmd:perm(Admin)"

    def func(self):
        result = reset_v52_playtest_state()
        if not result.get("success"):
            self.caller.msg(
                f"[V0.52 RESET] FAIL | reason={result.get('reason')} | build={DIRECT_D6_BUILD}"
            )
            return
        manifest = result.get("manifest")
        self.caller.msg(f"=== SIZA v0.52 RESET | {DIRECT_D6_BUILD} ===")
        self.caller.msg(
            f"PASS checked-manifest playtest reset | manifest={manifest.key}#{manifest.id} | analyzed=False"
        )
        self.caller.msg("Pista de analisis visible=False")
        self.caller.msg("No se tocaron estados de v0.51, jobs, NPCs, exits, skills ni Knowledge.")
        self.caller.msg("========================================================")
