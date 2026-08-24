from evennia import Command

from commands.world_input_v69_commands import CmdSizaValidateV69


QA_BUILD = "0.69.1-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.69 proposal semantics were correct, but qwen returned confidence=100 despite the 0..1 schema. "
            "The contract is now reinforced explicitly as decimal 0.0-1.0 with no percentage coercion; all catalog, hallucination rejection, UNSUPPORTED, live proposal and no-mutation checks run again."
        )
        _run_command(CmdSizaValidateV69, self.caller)
        self.caller.msg(
            "QA POLICY: v0.69 remains proposal-only. Invalid model contracts are rejected rather than silently normalized, and no accepted proposal executes or mutates world state."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
