from evennia import Command

from commands.world_input_v821_commands import CmdSizaValidateV821


QA_BUILD = "0.82.1-targeted-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.82 passed 12/12 for style sanitization, privacy, authoritative Fact transfer, grounded read-only rendering and older action regressions, but its manual voice comparison failed because FORMAL/RESERVED/TERSE and CASUAL/WARM/NORMAL produced nearly identical surface text. v0.82.1 changes only the presentation renderer: closed enums now map to closed high-signal delivery directives, a style-adherence guard rejects neutral output that ignores important voice cues, and a deterministic styled fallback preserves the exact Fact when qwen is safe but stylistically noncompliant. Running directive construction, style mismatch fallback, compliant acceptance, profile opposition, two live grounded renders and exact read-only state comparison."
        )
        _run_command(CmdSizaValidateV821, self.caller)
        self.caller.msg(
            "QA POLICY: v0.82.1 is presentation-only. The existing v0.81 factual grounding guard remains authoritative; the new style guard may only reject prose or select a deterministic non-factual delivery wrapper around the same Fact. If all targeted assertions pass, the previous v0.82 voice-quality gap is closed without a separate manual action."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
