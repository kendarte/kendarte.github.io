from evennia import Command

from commands.world_input_v70_commands import CmdSizaValidateV70


QA_BUILD = "0.70.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.70 introduces the first mutation bridge from an accepted LLM proposal into the real World Engine. "
            "Execution is restricted to high-confidence OBJECT_ACTION proposals, the current capability catalog is rebuilt immediately before dispatch, and the existing Object Action Engine rechecks locality, visibility, requirements and resolution. Running stale/hallucinated/low-confidence rejection, mechanical gate revalidation, one live qwen->engine dispatch, pending-resolution identity, duplicate protection, no-consequence-before-resolution and exact state restoration assertions."
        )
        _run_command(CmdSizaValidateV70, self.caller)
        self.caller.msg(
            "QA POLICY: this is a real mutation boundary, but v0.70 is not wired into normal player input. Automatic QA performs one controlled live dispatch and restores every touched field; manual gameplay acceptance begins only when the bridge is exposed to __nomatch in a later version."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
