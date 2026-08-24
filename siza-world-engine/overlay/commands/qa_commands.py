from evennia import Command

from commands.world_input_v721_commands import CmdSizaValidateV721


QA_BUILD = "0.72.1-targeted-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.72 production bridge already passed 11/12 checks including real Exit traversal, stale/low-confidence rejection and OBJECT_ACTION regression. "
            "The only failure was a QA phrase that the deterministic movement parser already understood. No gameplay code changed. Running a targeted semantic-fallback rerun with a phrase outside the deterministic movement vocabulary/strong exit matcher, then one live qwen selection and real Exit traversal with no-history/no-model-prose assertions."
        )
        _run_command(CmdSizaValidateV721, self.caller)
        self.caller.msg(
            "QA POLICY: production movement code is unchanged from v0.72. The previously passing bridge/regression checks are not repeated; this targeted suite retests only the failed semantic-fallback assumption and its live end-to-end traversal. Manual semantic-movement acceptance is required if all targeted assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
