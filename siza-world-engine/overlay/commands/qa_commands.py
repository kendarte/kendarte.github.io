from evennia import Command

from commands.world_input_v78_commands import CmdSizaValidateV78


QA_BUILD = "0.78.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.77 passed 16/16 for semantic SEARCH discovery->Knowledge projection. v0.78 closes the remaining semantic mismatch: deterministic active perception recognized by the existing parser now applies the same authored post-discovery Knowledge projection and rollback rules. The validator invokes the real v0.78 __nomatch command, verifies retrieval/idempotency/legacy compatibility/malformed rollback, and checks semantic SEARCH plus TALK/OBJECT routing preservation."
        )
        _run_command(CmdSizaValidateV78, self.caller)
        self.caller.msg(
            "QA POLICY: v0.78 exercises the real synchronous __nomatch deterministic-search path directly, including persistent discovery, Knowledge projection and normal retrieval, then restores every touched state. No separate manual v0.78 acceptance is required if all checks pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
