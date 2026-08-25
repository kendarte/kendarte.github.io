from evennia import Command

from commands.world_input_v90_commands import CmdSizaValidateV90


QA_BUILD = "0.90.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.89 is closed after its packet-contract follow-up passed 4/4. v0.90 closes a scaling gap in social Fact propagation: an authored SHARE_FACT rule must not send an NPC across the world to tell a target an exact Fact the target already knows, and a pending share must become stale if the target learns independently while the source is en route. The v0.89 transfer/contact authority is unchanged. refresh_fact_share_obligations now checks the target's authoritative Fact+Knowledge state before creating a share, retires an already-pending redundant obligation as completed_without_contact, and fact_driven_decision already runs that refresh before underlying candidate collection. Historical v0.59/v0.89 build IDs remain stable and v0.90 is exposed as a separate target-awareness capability. Running pre-known suppression, normal unknown-target materialization, independent-learning stale retirement, relationship-candidate removal, wrapper-order integration and one-shot anti-cycle behavior with exact state restoration."
        )
        _run_command(CmdSizaValidateV90, self.caller)
        self.caller.msg(
            "QA POLICY: v0.90 changes deterministic pre-decision social obligation materialization only. The validator proves both no-new-obligation and stale-pending retirement cases against real persistent Knowledge/Facts/relationships, confirms the fact-driven wrapper prunes before npc_decision candidate selection, checks no transfer history is fabricated and restores all touched state. qwen, transfer_knowledge_fact, relationship resolution, pathfinding and consequence engines are unchanged. No separate manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
