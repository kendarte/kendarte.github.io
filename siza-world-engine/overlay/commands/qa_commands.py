from evennia import Command

from commands.world_input_v83_commands import CmdSizaValidateV83


QA_BUILD = "0.83.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.82.1 closed the NPC voice-quality gap with 6/6 enforced style-delivery checks. v0.83 changes input routing only for explicit first-person Knowledge inspection such as 'qué sé sobre X': those requests now bypass Ollama and read deterministically from the player's already-known structured Facts. Unknown Facts with matching text remain gated by Knowledge level; output exposes only authored topic/text, never Fact IDs, Knowledge keys or provenance. General world questions remain on the existing viewer-grounded AI_INQUIRY path. Running parser precision, route separation, known/unknown privacy, real __nomatch rendering, multi-Fact behavior, exact read-only state comparison and object/perception/movement regressions."
        )
        _run_command(CmdSizaValidateV83, self.caller)
        self.caller.msg(
            "QA POLICY: v0.83 is deterministic/read-only. The validator invokes the real __nomatch Knowledge-query path and compares all touched player state before/after; no live Ollama or separate manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
