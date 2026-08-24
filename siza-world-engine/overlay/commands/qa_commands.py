from evennia import Command

from commands.world_object_v66_commands import CmdSizaValidateV66


QA_BUILD = "0.66.0-risk-based-one-command-qa"


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
            "RISK PROFILE: local Ollama HTTP integration added beyond the grounded v0.65 provider boundary. "
            "Running exact request mapping, leakage, parser/error handling, deterministic payload, live qwen3:8b call and no-persistence assertions."
        )
        _run_command(CmdSizaValidateV66, self.caller)
        self.caller.msg(
            "QA POLICY: because this is an LLM/network boundary, a successful automatic validator is followed by one visible real narration acceptance check."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
