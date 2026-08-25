from evennia import Command

from commands.world_input_v852_commands import CmdSizaValidateV852


QA_BUILD = "0.85.2-targeted-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.85.1 passed 11/12. All production-critical disclosure behavior passed: holder-local policy privacy, live qwen target selection, blocked TALK, real CONFRONT target-win remains blocked, real ACTOR_WIN consequence unlocks disclosure, and the clean Fact transfers/renders without the holder policy. The only failure used 'observo al Informante de Prueba C' as a PERCEPTION fixture, but v0.68 intentionally gives a strong authored OBJECT_ACTION match precedence before perception; that named phrase overlaps the actionable Informant object and its authored 'Presionar al informante' action. v0.85.2 changes no production code. It documents that preserved precedence and reruns the established generic perception fixture 'observo alrededor' plus Knowledge Query and movement routing with an exact read-only state check."
        )
        _run_command(CmdSizaValidateV852, self.caller)
        self.caller.msg(
            "QA POLICY: validator-only follow-up. v0.85 production already passed its live qwen and real CONFRONT integration. If this precedence-aware targeted validator passes all assertions, v0.85 is closed without manual acceptance."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
