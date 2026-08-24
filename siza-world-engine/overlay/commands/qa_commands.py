from evennia import Command

from commands.world_input_v69_commands import CmdSizaValidateV69


QA_BUILD = "0.69.0-risk-based-one-command-qa"


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
            "RISK PROFILE: free-form action interpretation is entering the LLM boundary, but execution remains disconnected. "
            "Running deterministic current-room capability catalogs, Ollama JSON-schema constrained structured outputs, hallucinated-capability rejection, kind mismatch rejection, explicit UNSUPPORTED behavior, two live qwen3:8b proposals and no-mutation assertions."
        )
        _run_command(CmdSizaValidateV69, self.caller)
        self.caller.msg(
            "QA POLICY: v0.69 is proposal-only. Even an accepted model proposal must not execute or mutate world state; execution is a separate future bridge."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
