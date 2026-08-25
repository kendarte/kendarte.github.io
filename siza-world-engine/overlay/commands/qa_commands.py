from evennia import Command

from commands.world_input_v92_commands import CmdSizaValidateV92


QA_BUILD = "0.92.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.91 is closed after the v0.91.1 compatibility follow-up restored the historical EXPLICIT source-loss packet at 3/3. v0.92 scales authored Fact propagation without changing local transfer authority: a fact_share_rule may now use target_mode=FACTION plus faction_id, resolving the current active faction members into independent normal SHARE_FACT obligations while excluding the source. Holder-local rule->obligation metadata lets membership churn cancel only branches whose targets no longer qualify; rejoining reactivates the same obligation id. Existing v0.90 target-aware pruning, v0.91 source-aware cancellation, relationship candidate resolution and transfer_knowledge_fact remain authoritative per target. The validator uses temporary faction memberships for Informant, Mara and Worker B, then restores all state."
        )
        _run_command(CmdSizaValidateV92, self.caller)
        self.caller.msg(
            "QA POLICY: v0.92 changes deterministic authored target expansion only. The validator covers faction fanout, source exclusion, independent obligation creation, relationship candidate integration, per-member cancellation/rejoin, one-recipient completion without affecting another pending recipient, multi-target source-loss cancellation, historical capability IDs and exact state restoration. qwen, pathfinding, npc_decision, relationship resolution and transfer_knowledge_fact are unchanged. No separate manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
