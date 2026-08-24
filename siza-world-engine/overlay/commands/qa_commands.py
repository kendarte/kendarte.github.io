from evennia import Command

from commands.world_input_v77_commands import CmdSizaValidateV77


QA_BUILD = "0.77.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.76 already passed 18/18 including live qwen SEARCH, real PER rolls and discovered_facts persistence. v0.77 adds only an authored post-discovery projection: a newly discovered perception fact may explicitly grant a Knowledge level and structured Knowledge Fact. qwen still sees only the generic SEARCH capability and player text. Running atomic projection, normal known-Fact retrieval, idempotency, legacy no-projection compatibility, malformed-projection rollback, one live qwen->PER->Knowledge path, and targeted regressions for visible OBSERVE, INTERACTION, OBJECT_ACTION and MOVEMENT."
        )
        _run_command(CmdSizaValidateV77, self.caller)
        self.caller.msg(
            "QA POLICY: v0.77 adds persistent Knowledge/Knowledge Fact mutation after a perception discovery, so automatic QA snapshots/restores discovered_facts, Knowledge, Knowledge Facts and room perception facts. A short manual search plus recall/inquiry acceptance check is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
