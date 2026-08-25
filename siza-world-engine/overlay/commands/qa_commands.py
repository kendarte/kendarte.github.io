from evennia import Command

from commands.world_input_v97_commands import CmdSizaValidateV97


QA_BUILD = "0.97.0-risk-based-one-command-qa"


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
            "RISK PROFILE: v0.96 is closed after its fact-specific lifecycle follow-up passed 3/3. v0.97 closes the next institutional authoring scale gap without changing Knowledge or SHARE_FACT authority: a faction fact_share_policy may keep the historical exact fact_id selector or may author one fact_type. A fact_type policy is deterministically projected into one managed rule per stored matching Fact, each carrying one exact fact_id before the existing v0.89-v0.95 source-awareness, target selection, travel/contact and transfer pipeline runs. Exact v0.96 policy rule IDs remain unchanged. Removing or re-adding one matching Fact removes/reactivates only its derived rule and normal obligation identity. Local overrides and inherited-policy conflicts continue to resolve per concrete fact_id. Policies with both fact_id and fact_type fail closed instead of silently choosing one selector."
        )
        _run_command(CmdSizaValidateV97, self.caller)
        self.caller.msg(
            "QA POLICY: v0.97 changes deterministic faction-policy projection only. The validator covers v0.96 exact-selector compatibility, one typed policy expanding to multiple concrete stored Facts, source Knowledge gating per derived exact Fact, later Knowledge activation, per-Fact removal/recovery with same identities, concrete local override, multi-faction conflicts and ambiguous-selector fail-closed behavior with exact state restoration. qwen, knowledge persistence, fact_share_rule selection, npc_decision, relationship resolution, transfer_knowledge_fact, pathfinding and consequence engines are unchanged. No separate manual acceptance is required if all assertions pass."
        )
        self.caller.msg("=== SIZA QA LATEST COMPLETE ===")
