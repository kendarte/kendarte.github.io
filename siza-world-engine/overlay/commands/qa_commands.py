from evennia import Command

from commands.world_input_v81_commands import CmdSizaValidateV81


QA_BUILD = "0.81.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.80.1 is closed after v0.80.3 proved the unchanged OBJECT_ACTION bridge reads the authored analyzed gate correctly. v0.81 adds presentation-only grounded NPC dialogue after an authoritative conversation has already selected and transferred an exact Fact. qwen receives only NPC name, player topic and the exact shared Fact text; Fact IDs, Knowledge keys and provenance stay private. A lexical grounding guard rejects new numbers/proper names or excessive novel content and falls back to authored text. Running transfer-before-render, provider-boundary privacy, unsafe-output fallback, transport fallback, one live qwen render with exact read-only state comparison, no-information/INFORM separation, and OBJECT_ACTION/MOVEMENT regressions."
        )
        _run_command(CmdSizaValidateV81, self.caller)
        self.caller.msg(
            "QA POLICY: v0.81 mutates no state after the authoritative v0.80 conversation transfer. The renderer is read-only and automatically falls back to authored Fact text on provider or grounding failure. The validator performs a live qwen render plus exact pre/post state comparison; no separate manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
