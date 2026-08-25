from evennia import Command

from commands.world_input_v831_commands import CmdSizaValidateV831


QA_BUILD = "0.83.1-targeted-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.83 passed 10/11. Its deterministic routing, known/unknown filtering, real __nomatch output, read-only behavior, multi-Fact handling and older route regressions all passed. The only failure was a validator false positive: it searched the serialized packet for the substring 'source', which also appears in the legitimate public metadata keys topic_source and retrieval_query_source. Production v0.83 already returns only public topic/text Fact rows. v0.83.1 changes no production code; it validates the packet structurally with exact allowlisted keys and exact forbidden provenance keys."
        )
        _run_command(CmdSizaValidateV831, self.caller)
        self.caller.msg(
            "QA POLICY: validator-only follow-up. If all structural privacy assertions pass, v0.83 is closed without manual acceptance."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
