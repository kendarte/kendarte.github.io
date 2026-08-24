from evennia import Command

from commands.world_input_v792_commands import CmdSizaValidateV792


QA_BUILD = "0.79.2-targeted-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.79.1 already passed the production-critical live path through qwen recipient selection and FACT_TRANSFERRED; its validator then crashed while json.dumps tried to serialize an Evennia _SaverList. v0.79.2 changes no production code. This targeted rerun clones persistent Saver containers to plain Python before JSON inspection, rechecks that model reason never persists, verifies transfer idempotency, and runs the PERCEPTION/INTERACTION/OBJECT_ACTION/MOVEMENT regressions that the prior validator did not reach."
        )
        _run_command(CmdSizaValidateV792, self.caller)
        self.caller.msg(
            "QA POLICY: this is a validator-only follow-up. The previous v0.79.1 run already proved the live qwen->recipient->authoritative FACT_TRANSFERRED path. If this targeted validator passes all assertions, v0.79.1 production INFORM is closed without a separate manual acceptance."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
