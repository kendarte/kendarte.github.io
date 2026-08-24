from evennia import Command

from commands.world_input_v82_commands import CmdSizaValidateV82


QA_BUILD = "0.82.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.81 is closed after its corrected semantic TALK fixture passed 4/4. v0.82 adds presentation-only NPC voice variation using explicit closed dialogue-style enums plus a neutral familiarity band derived from the existing relationship counter. Trait names/prose are never interpreted; only authored dialogue_effects with whitelisted enum dimensions can modify style. Fact selection/transfer still completes before rendering, qwen receives no IDs/provenance/private relationship data, and the v0.81 lexical grounding guard still owns factual safety. Running style sanitization, privacy, transfer-before-render, live two-profile grounded/read-only qwen rendering, no-information/INFORM separation, and PERCEPTION/OBJECT_ACTION/MOVEMENT regressions."
        )
        _run_command(CmdSizaValidateV82, self.caller)
        self.caller.msg(
            "QA POLICY: factual safety and state isolation are automatic. Voice quality is presentation/nondeterministic, so manual acceptance remains only for comparing the two LIVE V082 STYLE result lines printed by this validator."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
