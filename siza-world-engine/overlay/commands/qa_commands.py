from evennia import Command

from commands.world_input_v75_commands import CmdSizaValidateV75


QA_BUILD = "0.75.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.75 adds structured PERCEPTION execution only for a fresh visible OBSERVE capability. "
            "The bridge invokes the existing perception engine with the exact visible target and accepts only AUTO_SUCCESS with no roll, no discovery and no discovered_facts mutation; otherwise it restores the snapshot and rejects. Running deterministic-perception preservation, semantic fallback, provider-boundary privacy, low-confidence/stale rejection, live qwen target selection, no-mutation assertions, and INTERACTION/OBJECT_ACTION/MOVEMENT regressions."
        )
        _run_command(CmdSizaValidateV75, self.caller)
        self.caller.msg(
            "QA POLICY: v0.75 changes real player observation through async __nomatch but deliberately forbids perception rolls/discovery on the structured-proposal path. Automatic QA performs a live qwen OBSERVE selection and exact perception-engine execution while snapshotting/restoring all relevant state; a short manual semantic-observation acceptance check is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
