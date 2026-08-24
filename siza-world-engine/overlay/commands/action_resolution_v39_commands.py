from evennia import Command

from services.action_resolution_engine import (
    ACTION_RESOLUTION_BUILD,
    allowed_outcomes,
    begin_action_resolution,
    inspect_action_resolutions,
    resolve_action_resolution,
    set_adventure_stat,
)
from services.npc_simulation import find_npc


class CmdSizaValidateV39(Command):
    """Run the complete non-destructive v0.39 Action Resolution lifecycle validation."""

    key = "siza-validate-v39"
    aliases = ["validate-v39"]
    locks = "cmd:perm(Admin)"

    def func(self):
        query = (self.args or "").strip() or "Informante C"
        npc = find_npc(query)
        if not npc:
            self.caller.msg("[V0.39 VALIDATION] FAIL | no identifico el NPC de prueba.")
            return

        try:
            original_stats = {str(k): v for k, v in (npc.db.adventure_stats or {}).items()}
        except Exception:
            original_stats = {}
        try:
            original_history = list(npc.db.action_resolution_history or [])
        except Exception:
            original_history = []

        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            suffix = f" | {detail}" if detail else ""
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{suffix}")

        self.caller.msg(f"=== SIZA VALIDATION v0.39 | {ACTION_RESOLUTION_BUILD} ===")
        self.caller.msg(f"Harness NPC: {npc.key}")

        try:
            npc.db.adventure_stats = {}
            npc.db.action_resolution_history = []
            set_adventure_stat(npc, "PER", 4)

            started = begin_action_resolution(
                npc,
                {
                    "id": "VALIDATE-V39-DIRECT",
                    "trigger": "OBSTACLE",
                    "mode": "DIRECT",
                    "stat": "PER",
                    "difficulty": 7,
                },
                resolution_id="VALIDATE-V39-RES-001",
            )
            check(
                "check-enters-pending-resolution",
                started.get("status") == "PENDING_RESOLUTION"
                and started.get("resolved") is False
                and started.get("outcome") is None
                and started.get("actor_stat_value") == 4
                and started.get("difficulty") == 7,
                f"status={started.get('status')} stat={started.get('actor_stat_value')} difficulty={started.get('difficulty')}",
            )

            check(
                "mode-outcomes-are-explicit",
                allowed_outcomes("DIRECT") == ("SUCCESS", "FAILURE")
                and allowed_outcomes("CONFRONT") == ("ACTOR_WIN", "TARGET_WIN", "TIE")
                and allowed_outcomes("SYNCHRONIZE") == ("SYNC", "MISS")
                and allowed_outcomes("ACCUMULATE") == ("PROGRESS", "SETBACK", "COMPLETE", "FAILURE"),
                "no dice formula implied",
            )

            invalid = resolve_action_resolution(
                npc,
                "VALIDATE-V39-RES-001",
                "ACTOR_WIN",
                "VALIDATOR_EXTERNAL_PROVIDER",
                {"raw": "not-a-direct-outcome"},
            )
            after_invalid = inspect_action_resolutions(npc)
            current = (after_invalid.get("records") or [{}])[-1]
            check(
                "invalid-mode-outcome-is-rejected",
                invalid.get("status") == "INVALID_OUTCOME"
                and current.get("status") == "PENDING_RESOLUTION"
                and current.get("resolved") is False,
                f"status={invalid.get('status')} stored={current.get('status')}",
            )

            resolved = resolve_action_resolution(
                npc,
                "VALIDATE-V39-RES-001",
                "SUCCESS",
                "VALIDATOR_EXTERNAL_PROVIDER",
                {"test_value": 11, "test_threshold": 7},
            )
            check(
                "external-provider-can-resolve",
                resolved.get("status") == "RESOLVED"
                and resolved.get("resolved") is True
                and resolved.get("outcome") == "SUCCESS"
                and resolved.get("provider") == "VALIDATOR_EXTERNAL_PROVIDER"
                and (resolved.get("resolution_data") or {}).get("test_value") == 11,
                f"status={resolved.get('status')} outcome={resolved.get('outcome')} provider={resolved.get('provider')}",
            )

            duplicate = resolve_action_resolution(
                npc,
                "VALIDATE-V39-RES-001",
                "FAILURE",
                "SECOND_PROVIDER",
                {"attempt": 2},
            )
            check(
                "resolved-check-cannot-be-overwritten",
                duplicate.get("status") == "ALREADY_RESOLVED"
                and duplicate.get("outcome") == "SUCCESS"
                and duplicate.get("provider") == "VALIDATOR_EXTERNAL_PROVIDER",
                f"status={duplicate.get('status')} outcome={duplicate.get('outcome')}",
            )

            history = inspect_action_resolutions(npc)
            records = history.get("records") or []
            check(
                "resolution-is-persisted-in-history",
                history.get("count") == 1
                and len(records) == 1
                and records[0].get("resolution_id") == "VALIDATE-V39-RES-001"
                and records[0].get("status") == "RESOLVED",
                f"count={history.get('count')} status={(records[0] if records else {}).get('status')}",
            )
        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            npc.db.adventure_stats = original_stats
            npc.db.action_resolution_history = original_history

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(f"STATE RESTORED: stats + resolution history restored for {npc.key}")
        self.caller.msg("========================================================")
