from evennia import Command

from commands.world_input_v79_commands import CmdSizaValidateV79


QA_BUILD = "0.79.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.78 passed 10/10 and closed deterministic/semantic perception parity. v0.79 adds natural Known-Fact informing: qwen may select only a current visible TALK recipient; the topic comes only from player text, deterministic known-Fact retrieval may select exactly one Fact the player actually knows, and the existing transfer engine owns recipient Knowledge, provenance and the KNOWLEDGE_FACT_SHARED world action. Running real perception->Known Fact setup, provider-boundary privacy, low-confidence/unknown/stale rejection, live qwen recipient selection, authoritative transfer provenance, idempotency, and targeted PERCEPTION/INTERACTION/OBJECT_ACTION/MOVEMENT regressions."
        )
        _run_command(CmdSizaValidateV79, self.caller)
        self.caller.msg(
            "QA POLICY: v0.79 performs the complete live qwen recipient-selection and real transfer path after creating the source Fact through the real perception engine, then restores actor/NPC state and consequence-registry state exactly. No separate manual acceptance is required if all checks pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
