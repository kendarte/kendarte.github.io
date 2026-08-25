from evennia import Command

from commands.world_input_v851_commands import CmdSizaValidateV851


QA_BUILD = "0.85.1-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.84 is closed at 14/14. v0.85 connects disclosure to existing persistent NPC state instead of inventing a second social-resolution system. New policies are holder-local under npc.fact_disclosure_policies[fact_id], so willingness to reveal a Fact never travels with the transferable Fact itself; legacy inline v0.84 min_familiarity remains readable for compatibility. The validator uses the real v0.54 CONFRONT action: blocked TALK, forced target win remains blocked, forced actor win flows through the existing consequence engine and sets v054_pressure_conceded, then the same live qwen-selected TALK target transfers and renders the now-authorized clean Fact. qwen never receives Fact text, holder policy or confrontation state."
        )
        _run_command(CmdSizaValidateV851, self.caller)
        self.caller.msg(
            "QA POLICY: v0.85 changes conversation authority and consumes persistent state, so this targeted validator performs a live qwen target-selection roundtrip plus real CONFRONT failure/success resolution, exact state restoration, holder-policy privacy and clean-Fact transfer checks. No separate manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
