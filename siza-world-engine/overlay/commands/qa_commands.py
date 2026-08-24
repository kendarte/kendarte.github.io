from evennia import Command

from commands.world_input_v741_commands import CmdSizaValidateV741


QA_BUILD = "0.74.1-targeted-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.74 passed 12/13 checks; the only failure was routing precedence for an explicit TALK sentence containing an object noun. "
            "v0.74.1 adds a narrow wrapper: parse_interaction_intent TALK wins before weak object ambiguity can reach qwen, while the semantic topic fallback remains unchanged. Running targeted explicit-TALK classification, exact real __nomatch execution through the existing Knowledge-gated interaction engine, semantic-fallback preservation and OBJECT_ACTION routing regression."
        )
        _run_command(CmdSizaValidateV741, self.caller)
        self.caller.msg(
            "QA POLICY: v0.74 Knowledge/privacy/live-qwen behavior already passed 12 checks and production topic/bridge code is unchanged. This targeted rerun validates only the new explicit-TALK precedence wrapper and restores all touched social/Knowledge state. Manual topic-conversation acceptance is required if all targeted assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
