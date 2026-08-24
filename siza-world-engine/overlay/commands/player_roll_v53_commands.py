from evennia import Command

from services.action_resolution_engine import adventure_stats, normalize_stat_key, set_adventure_stat
from services.player_roll_resolution_engine import PLAYER_ROLL_BUILD, resolve_pending_object_action_roll
from world.upgrade_pilot_v53 import reset_v53_playtest_state


PLAYTEST_BACKUP_ATTR = "playtest_stat_backups"


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


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
            base += f" | progreso={packet.get('progress_after')}/{packet.get('progress_goal')}"
        self.caller.msg(base)


class CmdSizaSelfStatTemp(Command):
    """Admin/playtest: save the exact current stat state once, then set a temporary value."""

    key = "siza-self-stat-temp"
    aliases = ["self-stat-temp"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().split()
        if len(parts) != 2:
            self.caller.msg("Uso: siza-self-stat-temp <FUE|AGI|COO|INT|PER|PSI> <VALUE>")
            return
        stat = normalize_stat_key(parts[0])
        if not stat:
            self.caller.msg("[SELF STAT TEMP DENIED] reason=BAD_STAT")
            return

        current_stats = adventure_stats(self.caller)
        backups = _plain_dict(getattr(self.caller.db, PLAYTEST_BACKUP_ATTR, {}))
        if stat not in backups:
            backups[stat] = {
                "existed": stat in current_stats,
                "value": current_stats.get(stat),
            }
            setattr(self.caller.db, PLAYTEST_BACKUP_ATTR, backups)

        packet = set_adventure_stat(self.caller, stat, parts[1])
        if not packet.get("success"):
            self.caller.msg(f"[SELF STAT TEMP DENIED] reason={packet.get('reason')}")
            return
        backup = backups.get(stat) or {}
        original = backup.get("value") if backup.get("existed") else "UNSET"
        self.caller.msg(
            f"[SELF STAT TEMP] {stat} | original={original} | temporary={packet.get('after')}"
        )


class CmdSizaSelfStatRestore(Command):
    """Admin/playtest: restore exactly the stat value/presence saved by self-stat-temp."""

    key = "siza-self-stat-restore"
    aliases = ["self-stat-restore"]
    locks = "cmd:perm(Admin)"

    def func(self):
        stat = normalize_stat_key((self.args or "").strip())
        if not stat:
            self.caller.msg("Uso: siza-self-stat-restore <FUE|AGI|COO|INT|PER|PSI>")
            return

        backups = _plain_dict(getattr(self.caller.db, PLAYTEST_BACKUP_ATTR, {}))
        if stat not in backups:
            self.caller.msg(f"[SELF STAT RESTORE] {stat} | NO_BACKUP")
            return

        backup = _plain_dict(backups.get(stat))
        stats = adventure_stats(self.caller)
        before = stats.get(stat) if stat in stats else "UNSET"
        if bool(backup.get("existed")):
            stats[stat] = backup.get("value")
            restored = backup.get("value")
        else:
            stats.pop(stat, None)
            restored = "UNSET"
        self.caller.db.adventure_stats = stats

        backups.pop(stat, None)
        if backups:
            setattr(self.caller.db, PLAYTEST_BACKUP_ATTR, backups)
        else:
            try:
                self.caller.attributes.remove(PLAYTEST_BACKUP_ATTR)
            except Exception:
                setattr(self.caller.db, PLAYTEST_BACKUP_ATTR, {})

        self.caller.msg(f"[SELF STAT RESTORE] {stat} | {before} -> {restored}")


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
