from evennia import Command

from commands.world_input_v911_commands import CmdSizaValidateV911


QA_BUILD = "0.91.1-targeted-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.91 previously passed its production path, then a work-in-progress v0.92 multi-target extension changed the SOURCE_DOES_NOT_KNOW_FACT refresh packet from one direct obligation_id to a cancelled_obligations list. Authoritative state remained correct: the obligation cancelled, no relationship candidate survived, relearning reactivated the same id and local transfer still completed. v0.91.1 restores backward-compatible EXPLICIT packet fields while retaining the additive multi-target metadata. Production social authority is otherwise unchanged. Running only the two packet/candidate regressions that failed plus same-id reactivation."
        )
        _run_command(CmdSizaValidateV911, self.caller)
        self.caller.msg(
            "QA POLICY: targeted compatibility follow-up. The earlier v0.91 run already re-proved cancellation, no movement/transfer while source-unaware, same-id recovery and final local transfer. This validator checks only the EXPLICIT refresh packet contract accidentally changed by work-in-progress v0.92 plus candidate pruning and reactivation. No manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
