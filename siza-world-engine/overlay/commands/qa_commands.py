from evennia import Command

from commands.world_input_v72_commands import CmdSizaValidateV72


QA_BUILD = "0.72.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.72 expands the real async structured-proposal path from OBJECT_ACTION to MOVEMENT. "
            "A movement proposal must be accepted, high-confidence and present in a freshly rebuilt current-room catalog; the bridge then resolves the exact current Evennia Exit and executes that Exit command rather than moving directly. Running deterministic movement preservation, semantic fallback, low-confidence/stale rejection, OBJECT_ACTION regression, live qwen movement selection, exact traversal and no-model-prose/state assertions."
        )
        _run_command(CmdSizaValidateV72, self.caller)
        self.caller.msg(
            "QA POLICY: v0.72 changes real player movement through async __nomatch. Automatic QA performs controlled real Exit traversals and restores location/state; a short manual semantic-movement acceptance check is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
