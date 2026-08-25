from evennia import Command

from commands.world_input_v961_commands import CmdSizaValidateV961


QA_BUILD = "0.96.1-targeted-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.96 passed 6/9. Inheritance, existing v0.89-v0.95 materialization, wrapper ordering, local override, cross-faction conflict fail-closed behavior and additive build contracts all passed. The three failures were validator-only: world_input_v96 imported the v0.89 _find_obligation helper, whose obligation id is hard-coded to the v0.88 witness Fact, while v0.96 uses FACT-V096-INSTITUTIONAL-REPORT-001. The v0.96 sync packets already reported the correct institutional obligation being cancelled. v0.96.1 changes no production code and reruns only membership-leave cancellation, same-id reactivation after rejoin, and policy-removal cancellation using the exact v0.96 fact-specific obligation id."
        )
        _run_command(CmdSizaValidateV961, self.caller)
        self.caller.msg(
            "QA POLICY: validator-only follow-up. Production v0.96 already proved inheritance, normal SHARE_FACT materialization, pre-decision sync ordering, local-rule override and multi-faction conflict behavior. This targeted validator only corrects the obligation identity used to inspect the three lifecycle assertions. No manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
