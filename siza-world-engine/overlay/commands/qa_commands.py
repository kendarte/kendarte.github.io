from evennia import Command

from commands.world_input_v76_commands import CmdSizaValidateV76


QA_BUILD = "0.76.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.76 adds semantic active PERCEPTION with a generic current-room SEARCH capability that exposes no hidden perception facts to qwen. "
            "The bridge derives the search target only from player text, revalidates the current room, then delegates PER roll, difficulty, discovery and discovered_facts persistence to the existing perception engine. Running deterministic-search preservation, semantic fallback, provider-boundary privacy, low-confidence/stale rejection, guaranteed miss/success/idempotency, live qwen room-search selection, exact persistence assertions and regressions for visible OBSERVE, INTERACTION, OBJECT_ACTION and MOVEMENT."
        )
        _run_command(CmdSizaValidateV76, self.caller)
        self.caller.msg(
            "QA POLICY: v0.76 enables a real persistent discovery mutation through async __nomatch. Automatic QA isolates temporary room perception facts, forces both guaranteed miss and guaranteed success ranges, performs one live qwen SEARCH selection, verifies discovered_facts persistence/idempotency, then restores every touched state. Manual semantic active-search acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
