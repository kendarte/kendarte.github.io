from evennia import Command

from commands.world_input_v80_commands import CmdSizaValidateV80
from commands.world_input_v801_commands import CmdSizaValidateV801


QA_BUILD = "0.80.1-risk-based-one-command-qa"


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
    """Run the newest risk-based validators; manual acceptance is only required when risk remains."""

    key = "siza-qa-latest"
    aliases = ["qa-latest"]
    locks = "cmd:perm(Admin)"

    def func(self):
        self.caller.msg(f"=== SIZA QA LATEST | {QA_BUILD} ===")
        self.caller.msg(
            "RISK PROFILE: v0.79.1 is closed. v0.80 makes an NPC Fact that the existing interaction engine actually shared become persistent player Knowledge through the authoritative transfer engine. v0.80.1 adds the missing production async wiring so semantic AI_ACTION_PROPOSAL callbacks also pass through the v0.80 acquisition handler. Explicit TALK remains deterministic; semantic TALK lets qwen select only the visible NPC target; qwen never receives or authors Facts."
        )
        _run_command(CmdSizaValidateV80, self.caller)
        _run_command(CmdSizaValidateV801, self.caller)
        self.caller.msg(
            "QA POLICY: v0.80 exercises deterministic/semantic acquisition, provenance, retrieval, idempotency, no-information/greeting non-acquisition, INFORM separation and older action regressions. v0.80.1 separately performs a live qwen semantic TALK target-selection callback through the exact new wiring. No separate manual acceptance is required if both validator result blocks pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
