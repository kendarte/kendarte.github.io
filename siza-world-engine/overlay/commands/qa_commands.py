from evennia import Command

from commands.world_input_v73_commands import CmdSizaValidateV73


QA_BUILD = "0.73.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.73 expands structured async fallback to INTERACTION while deliberately keeping semantic topics disabled. "
            "The model may select only a current visible TALK capability; the bridge rebuilds the current catalog, confirms the NPC is still local/visible, then converts the selection into a canonical TALK intent for the existing interaction engine. Running deterministic-talk preservation, semantic fallback, low-confidence rejection, NPC-moved stale rejection, real memory/relationship mutation, Knowledge/Fact isolation, live qwen target selection, and OBJECT_ACTION/MOVEMENT regressions."
        )
        _run_command(CmdSizaValidateV73, self.caller)
        self.caller.msg(
            "QA POLICY: v0.73 changes real player social input and persistent memory/relationship state. Automatic QA snapshots/restores both actor and NPC social state; a short real __nomatch interaction acceptance check is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
