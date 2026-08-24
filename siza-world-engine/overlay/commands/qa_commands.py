from evennia import Command

from commands.world_input_v71_commands import CmdSizaValidateV71


QA_BUILD = "0.71.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.71 exposes structured action proposals to the real __nomatch path for inputs that v0.68 previously classified as unknown. "
            "Capabilities are snapshotted on the Evennia reactor, HTTP/JSON runs on a worker using plain dicts only, and the callback returns to the reactor where v0.70 rebuilds the current catalog and the existing Object Action Engine rechecks mechanics. Running deterministic-route preservation, inquiry separation, unknown-action upgrade, unsupported/low-confidence/stale rejection, live prebuilt qwen proposal, real pending-resolution dispatch, deterministic renderer and no-model-prose-persistence assertions."
        )
        _run_command(CmdSizaValidateV71, self.caller)
        self.caller.msg(
            "QA POLICY: v0.71 changes real player input and asynchronous execution scheduling. Automatic QA validates the full snapshot->proposal->bridge data path; a short manual __nomatch acceptance check is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
