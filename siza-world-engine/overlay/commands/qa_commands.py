from evennia import Command

from commands.world_input_v68_commands import CmdSizaValidateV68


QA_BUILD = "0.68.1-risk-based-one-command-qa"


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
            "RISK PROFILE: real __nomatch player input now gains an Ollama fallback, with an additional guard against old token matchers treating questions as mutating actions. "
            "Running strong object-action routing, interaction/perception/movement precedence, strong-inquiry mutation blocking, inquiry-only AI gating, unknown-action rejection, viewer-private Fact isolation, async-dispatch contract, live qwen3:8b narration and no-persistence assertions."
        )
        _run_command(CmdSizaValidateV68, self.caller)
        self.caller.msg(
            "QA POLICY: because this changes the real player input router, successful automatic QA is followed by a short real-input acceptance check of the critical branches only."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
