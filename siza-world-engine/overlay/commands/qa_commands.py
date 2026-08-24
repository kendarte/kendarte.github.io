from evennia import Command

from commands.world_input_v74_commands import CmdSizaValidateV74


QA_BUILD = "0.74.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.74 allows semantic TALK fallback to carry an explicit conversation topic, but qwen still selects only the current visible NPC. "
            "Topic text is extracted deterministically from the original player input, never from model reason; the request boundary still excludes NPC Knowledge/Facts. The existing interaction engine then applies the NPC Knowledge gate and chooses the Fact response. Running deterministic talk preservation, player-topic extraction, provider-boundary privacy, blocked/allowed Knowledge levels, modern Fact.text compatibility, stale-NPC rejection, live qwen target selection, greeting regression and OBJECT_ACTION/MOVEMENT regressions."
        )
        _run_command(CmdSizaValidateV74, self.caller)
        self.caller.msg(
            "QA POLICY: v0.74 touches persistent social memory and authorized Fact disclosure. Automatic QA isolates a temporary modern Fact, tests both denied and allowed Knowledge levels, performs one live qwen target-selection path, and restores actor/NPC state exactly. A short manual topic-conversation acceptance check is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
