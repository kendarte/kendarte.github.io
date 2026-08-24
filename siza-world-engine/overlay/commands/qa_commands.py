from evennia import Command

from commands.decision_commands import CmdSizaDecide, CmdSizaDecisionStep
from commands.world_object_v59_commands import CmdSizaFactGoalsV59
from commands.world_object_v61_commands import CmdSizaResetV61
from commands.world_object_v62_commands import CmdSizaValidateV62


QA_BUILD = "0.62.0-one-command-qa"


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
    """Run the current manual acceptance sequence and newest automatic validator."""

    key = "siza-qa-latest"
    aliases = ["qa-latest"]
    locks = "cmd:perm(Admin)"

    def func(self):
        self.caller.msg(f"=== SIZA QA LATEST | {QA_BUILD} ===")
        self.caller.msg("PHASE 1/2: v0.61 integration acceptance")

        _run_command(CmdSizaResetV61, self.caller)
        _run_command(CmdSizaFactGoalsV59, self.caller, "Mara")
        _run_command(CmdSizaDecide, self.caller, "Mara")
        _run_command(CmdSizaDecisionStep, self.caller, "Mara")
        _run_command(CmdSizaDecisionStep, self.caller, "Mara")
        _run_command(CmdSizaDecisionStep, self.caller, "Mara")
        _run_command(CmdSizaFactGoalsV59, self.caller, "Mara")
        _run_command(CmdSizaDecide, self.caller, "Mara")

        self.caller.msg("PHASE 2/2: newest automatic validator v0.62")
        _run_command(CmdSizaValidateV62, self.caller)
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
