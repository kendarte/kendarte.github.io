from evennia import Command

from commands.world_input_v80_commands import CmdSizaValidateV80


QA_BUILD = "0.80.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.79.1 is closed. v0.80 makes an NPC Fact that the existing interaction engine actually shared become persistent player Knowledge through the existing authoritative transfer engine. Explicit TALK remains deterministic; semantic TALK still lets qwen select only the visible NPC target. The model never receives Knowledge/Facts and never chooses fact_id/content. Running explicit and semantic acquisition, provenance, retrieval, idempotency, no-information/greeting non-acquisition, INFORM separation, provider-boundary privacy, and PERCEPTION/OBJECT_ACTION/MOVEMENT regressions."
        )
        _run_command(CmdSizaValidateV80, self.caller)
        self.caller.msg(
            "QA POLICY: v0.80 uses the real interaction engine and real Fact transfer in both deterministic and semantic TALK fixtures, snapshots/restores persistent Knowledge/social/consequence state, and exercises all changed boundaries automatically. No separate manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
