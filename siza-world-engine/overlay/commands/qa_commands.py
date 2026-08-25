from evennia import Command

from commands.world_input_v93_commands import CmdSizaValidateV93


QA_BUILD = "0.93.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.92 is closed at 8/8 after proving one authored FACTION Fact-share rule expands into independent SHARE_FACT branches for current active members while preserving per-target transfer authority. v0.93 adds an optional deterministic min_authority filter to that same FACTION target mode, using the existing faction membership_authority value rather than a new hierarchy system. Omitting min_authority preserves v0.92 behavior exactly. Rank/authority changes dynamically remove or reactivate only affected pending branches; malformed authority thresholds fail closed by cancelling already-pending branches from that rule until configuration is corrected. Historical v0.89-v0.92 capability IDs remain stable. The validator uses temporary authority-bearing memberships for Informant, Mara and Worker B and restores all touched state."
        )
        _run_command(CmdSizaValidateV93, self.caller)
        self.caller.msg(
            "QA POLICY: v0.93 changes deterministic faction-recipient filtering only. The validator covers threshold selection, holder-local rule provenance, v0.92 no-filter compatibility, below-threshold branch pruning, promotion-driven same-id reactivation, malformed-filter fail-closed cancellation and correction-driven recovery with exact state restoration. qwen, npc_decision, relationship resolution, transfer_knowledge_fact, pathfinding and consequence engines are unchanged. No separate manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
