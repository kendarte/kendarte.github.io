from evennia import Command

from commands.world_input_v1011_commands import CmdSizaValidateV1011


QA_BUILD = "1.01.1-targeted-risk-based-one-command-qa"


def _run_command(command_cls, caller, args=""):
    """Run one existing synchronous Evennia command against the real caller."""
    cmd = command_cls()
    cmd.caller = caller
    cmd.args = str(args or "")
    cmd.raw_string = f"{cmd.key} {cmd.args}".strip()
    cmd.cmdstring = cmd.key
    try:
        cmd.account = caller.account
    except Exception:
        pass
    try:
        sessions = list(caller.sessions.all())
        cmd.session = sessions[0] if sessions else None
    except Exception:
        cmd.session = None
    return cmd.func()


class CmdSizaQALatest(Command):
    """Run the newest risk-based validator; manual acceptance is only required when risk remains."""

    key = "siza-qa-latest"
    aliases = ["qa-latest"]
    locks = "cmd:perm(Admin)"

    def func(self):
        self.caller.msg(f"=== SIZA QA LATEST | {QA_BUILD} ===")
        self.caller.msg(
            "RISK PROFILE: v1.01 production passed 9/10. RETRACTED/SUPERSEDED lifecycle authority, retrieval/disclosure/decision-effect exclusion, Fact-goal cancellation, SHARE_FACT cancellation, transfer blocking, same-identity reactivation, holder-local copy isolation and replacement semantics all passed. The sole failure was validator setup: its baseline required a relationship candidate but did not control npc.db.decision_enabled, while collect_relationship_candidates intentionally returns [] for a decision-disabled NPC. The goal and SHARE_FACT obligation were visibly active in the failed assertion. v1.01.1 changes no production code and reruns only the active-Fact baseline with decision_enabled explicitly enabled and restored."
        )
        _run_command(CmdSizaValidateV1011, self.caller)
        self.caller.msg(
            "QA POLICY: targeted validator-only follow-up. If all three assertions pass, the automated v1.01 lifecycle suite is closed. Because v1.01 changed shared/core fact_knowledge_state authority, one minimal player-facing retract/reactivate acceptance remains before freezing the engine."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
