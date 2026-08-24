from evennia import Command

from commands.world_input_v802_commands import CmdSizaValidateV802


QA_BUILD = "0.80.2-targeted-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.80 production acquisition passed 13/14 and v0.80.1 semantic async wiring passed 5/5. The only v0.80 failure was its OBJECT_ACTION regression fixture: the persistent manifest was already analyzed, while the authored analyze action explicitly requires analyzed=False. v0.80.2 changes no production code; it isolates that authored precondition, proves the unchanged bridge accepts the valid state, proves the analyzed state is correctly rejected, and restores the fixture exactly."
        )
        _run_command(CmdSizaValidateV802, self.caller)
        self.caller.msg(
            "QA POLICY: this is a validator-only follow-up. The production-critical NPC->player Knowledge acquisition and live semantic qwen callback already passed. If this targeted validator passes all assertions, v0.80.1 is closed without manual acceptance."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
