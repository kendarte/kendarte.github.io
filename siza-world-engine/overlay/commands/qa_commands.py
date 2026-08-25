from evennia import Command

from commands.world_input_v891_commands import CmdSizaValidateV891


QA_BUILD = "0.89.1-targeted-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.89 passed 9/10. Every production-critical behavior passed: the witness Fact created a SHARE_FACT obligation, the relationship candidate targeted Mara dynamically, the Informant traversed to Mara, Mara learned the exact Fact with direct-local transfer history, and the obligation completed one-shot without reactivation. The only failure asserted relationship_kind/fact_shared on the top-level npc_decision packet, but npc_decision historically projects relationship completions generically as completion_source=RELATIONSHIP plus relationship_resolved/reason/obligation/target and does not expose relationship-specific payload fields. v0.89.1 changes no production code. It validates SHARE_FACT identity before execution on the authoritative obligation/candidate, then validates decision completion against npc_decision's real packet contract and proves the exact Fact transfer from persistent post-state."
        )
        _run_command(CmdSizaValidateV891, self.caller)
        self.caller.msg(
            "QA POLICY: validator-only follow-up. Production v0.89 already demonstrated physical traversal, exact Fact transfer, preserved provenance and one-shot completion. This targeted rerun only corrects the packet-shape assertion and re-proves the relationship completion plus authoritative transfer state. If all assertions pass, v0.89 is closed without manual acceptance."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
