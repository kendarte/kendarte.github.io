from evennia import Command

from commands.world_input_v803_commands import CmdSizaValidateV803


QA_BUILD = "0.80.3-targeted-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.80 production acquisition passed its NPC->player Knowledge path and v0.80.1 semantic async wiring passed 5/5. v0.80.2 then proved the valid OBJECT_ACTION outer handler returned WORLD_ENGINE_ACCEPTED, but its validator read world_engine_status at the outer level even though v0.71 intentionally wraps the authoritative bridge packet under result['bridge']. v0.80.3 changes no production code; it reads the established nested bridge shape, proves the valid analyzed=False action enters PENDING_RESOLUTION, proves analyzed=True returns OBJECT_ACTION_REQUIREMENTS_UNMET with an OBJECT_STATE blocker, and restores the fixture exactly."
        )
        _run_command(CmdSizaValidateV803, self.caller)
        self.caller.msg(
            "QA POLICY: validator-only follow-up. No production bridge, interaction, Knowledge, transfer or qwen code changed. If all targeted assertions pass, v0.80.1 is closed without manual acceptance."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
