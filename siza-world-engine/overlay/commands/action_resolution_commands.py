from evennia import Command

from services.action_resolution_engine import (
    ACTION_RESOLUTION_BUILD,
    action_requires_resolution,
    inspect_adventure_stats,
    prepare_action_check,
    set_adventure_stat,
)
from services.npc_simulation import find_npc


class CmdSizaStats(Command):
    """Inspect explicitly authored Adventure stats for one NPC."""

    key = "siza-stats"
    aliases = ["adventure-stats"]
    locks = "cmd:all()"

    def func(self):
        query = (self.args or "").strip()
        npc = find_npc(query)
        if not npc:
            self.caller.msg("Uso: siza-stats <NPC>")
            return

        packet = inspect_adventure_stats(npc)
        self.caller.msg(f"=== SIZA ADVENTURE STATS | {packet.get('build')} ===")
        self.caller.msg(f"NPC: {npc.key} | npc_id={packet.get('npc_id')}")
        for key, value in (packet.get("stats") or {}).items():
            text = "UNSET" if value is None else str(value)
            self.caller.msg(f"  {key}={text}")
        self.caller.msg(f"authored_count={packet.get('authored_count')}")
        self.caller.msg("================================================")


class CmdSizaStatSet(Command):
    """Admin/debug: persist one Adventure stat without inventing defaults for the others."""

    key = "siza-stat-set"
    aliases = ["adventure-stat-set"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = (self.args or "").strip().rsplit(" ", 2)
        if len(parts) != 3:
            self.caller.msg("Uso: siza-stat-set <NPC> <FUE|AGI|COO|INT|PER|PSI> <VALUE>")
            return
        npc_query, stat, value = parts
        npc = find_npc(npc_query.strip())
        if not npc:
            self.caller.msg("No identifico ese NPC de Siza.")
            return
        packet = set_adventure_stat(npc, stat, value)
        if not packet.get("success"):
            self.caller.msg(f"[STAT DENIED] reason={packet.get('reason')}")
            return
        self.caller.msg(
            f"[STAT SET] {npc.key} | {packet.get('stat')} | "
            f"{packet.get('before')} -> {packet.get('after')}"
        )


class CmdSizaCheckContract(Command):
    """Admin/debug: validate an authored check packet without resolving a dice formula."""

    key = "siza-check-contract"
    aliases = ["check-contract"]
    locks = "cmd:perm(Admin)"

    def func(self):
        parts = [part.strip() for part in (self.args or "").split("|")]
        if len(parts) not in {4, 6} or not all(parts[:4]):
            self.caller.msg(
                "Uso: siza-check-contract <ACTOR NPC> | <TRIGGER> | <MODE> | <STAT> "
                "[| <TARGET NPC> | <TARGET_STAT>]"
            )
            return

        actor = find_npc(parts[0])
        if not actor:
            self.caller.msg("No identifico ACTOR NPC.")
            return

        target = None
        target_stat = None
        if len(parts) == 6:
            target = find_npc(parts[4])
            target_stat = parts[5]
            if not target:
                self.caller.msg("No identifico TARGET NPC.")
                return

        spec = {
            "id": "ADMIN-CHECK-CONTRACT",
            "trigger": parts[1],
            "mode": parts[2],
            "stat": parts[3],
        }
        if target_stat:
            spec["target_stat"] = target_stat

        packet = prepare_action_check(actor, spec, target=target)
        check = packet.get("check") or {}
        self.caller.msg(f"=== SIZA CHECK CONTRACT | {ACTION_RESOLUTION_BUILD} ===")
        self.caller.msg(
            f"status={packet.get('status')} | trigger={check.get('trigger')} | "
            f"mode={check.get('mode')} | actor={packet.get('actor')} | "
            f"stat={packet.get('actor_stat')} value={packet.get('actor_stat_value')}"
        )
        if target:
            self.caller.msg(
                f"target={packet.get('target')} | stat={packet.get('target_stat')} "
                f"value={packet.get('target_stat_value')}"
            )
        self.caller.msg(
            f"resolved={packet.get('resolved', False)} | outcome={packet.get('outcome')} | "
            f"reason={packet.get('reason')}"
        )
        if check.get("errors"):
            self.caller.msg(f"errors={check.get('errors')}")
        self.caller.msg("=================================================")


class CmdSizaValidateV38(Command):
    """Run the complete non-destructive v0.38 Adventure Stats / Check Contract validation."""

    key = "siza-validate-v38"
    aliases = ["validate-v38"]
    locks = "cmd:perm(Admin)"

    def func(self):
        query = (self.args or "").strip() or "Informante C"
        npc = find_npc(query)
        if not npc:
            self.caller.msg("[V0.38 VALIDATION] FAIL | no identifico el NPC de prueba.")
            return

        try:
            original_stats = {str(k): v for k, v in (npc.db.adventure_stats or {}).items()}
        except Exception:
            original_stats = {}

        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            suffix = f" | {detail}" if detail else ""
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{suffix}")

        self.caller.msg(f"=== SIZA VALIDATION v0.38 | {ACTION_RESOLUTION_BUILD} ===")
        self.caller.msg(f"Harness NPC: {npc.key}")

        try:
            # Test from a clean temporary stat state, then restore exactly what was there.
            npc.db.adventure_stats = {}
            empty = inspect_adventure_stats(npc)
            values = empty.get("stats") or {}
            check(
                "stats-unset-are-not-zero",
                empty.get("authored_count") == 0 and all(value is None for value in values.values()),
                f"authored_count={empty.get('authored_count')}",
            )

            set_packet = set_adventure_stat(npc, "PER", 4)
            after = inspect_adventure_stats(npc)
            after_values = after.get("stats") or {}
            check(
                "single-stat-persists",
                bool(set_packet.get("success"))
                and after_values.get("PER") == 4
                and after.get("authored_count") == 1
                and all(after_values.get(key) is None for key in ("FUE", "AGI", "COO", "INT", "PSI")),
                f"PER={after_values.get('PER')} authored_count={after.get('authored_count')}",
            )

            ready = prepare_action_check(
                npc,
                {
                    "id": "VALIDATE-V38-PER",
                    "trigger": "OBSTACLE",
                    "mode": "ACCUMULATE",
                    "stat": "PER",
                },
            )
            check(
                "authored-check-contract-ready",
                ready.get("status") == "READY_UNRESOLVED"
                and ready.get("actor_stat") == "PER"
                and ready.get("actor_stat_value") == 4
                and ready.get("resolved") is False
                and ready.get("outcome") is None
                and ready.get("reason") == "FORMULA_NOT_AUTHORED",
                f"status={ready.get('status')} value={ready.get('actor_stat_value')} reason={ready.get('reason')}",
            )

            missing = prepare_action_check(
                npc,
                {
                    "id": "VALIDATE-V38-FUE",
                    "trigger": "OBSTACLE",
                    "mode": "ACCUMULATE",
                    "stat": "FUE",
                },
            )
            check(
                "missing-stat-blocks-check",
                missing.get("status") == "MISSING_ACTOR_STAT" and missing.get("actor_stat") == "FUE",
                f"status={missing.get('status')}",
            )

            no_check = action_requires_resolution({"id": "ROUTINE-NO-CHECK"})
            explicit_check = action_requires_resolution(
                {
                    "id": "OBSTACLE-WITH-CHECK",
                    "check": {
                        "trigger": "OBSTACLE",
                        "mode": "DIRECT",
                        "stat": "PER",
                    },
                }
            )
            check(
                "resolution-is-explicit-not-routine-default",
                no_check is False and explicit_check is True,
                f"routine={no_check} authored_obstacle={explicit_check}",
            )
        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            npc.db.adventure_stats = original_stats

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(f"STATE RESTORED: adventure_stats restored for {npc.key}")
        self.caller.msg("========================================================")
